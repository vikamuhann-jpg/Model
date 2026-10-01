"""Fund tracing over the transaction graph (FR-05).

The pipeline already builds a transaction graph, but only inside
:mod:`flowguard.features.gfp`, and only to emit feature vectors. Nothing could
answer the question PS9 actually leads with: *given this account, where did the
money go?*

This module answers it, and it is the one capability in the product plan that is
**independent of detector quality** -- a traversal is correct or incorrect
regardless of how good the model is.

Three properties shape the implementation:

* **Funds only flow forward in time.** A neighbour walk that ignores timestamps
  will happily construct a path where money arrives at an account after it
  supposedly left, and present it as a chain. Every hop here is constrained to a
  non-decreasing (forward) or non-increasing (backward) timestamp.
* **Traversal must be bounded.** ADR-013 measured a real network whose
  99.9th-percentile degree is 1,034 and whose maximum is 11,152. An uncapped
  breadth-first walk through such a vertex does not terminate usefully, and with
  a per-vertex cap alone the frontier still grows as ``cap ** horizon``. Both a
  per-vertex cap and a total edge budget are enforced, and both are reported.
* **Commingled funds cannot be attributed.** Once money lands in an account it is
  indistinguishable from the balance already there. This module reports the
  amounts observed on each hop and does **not** claim which specific funds moved
  on; see :meth:`TraceResult.per_hop`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from flowguard.data import schema as S

FORWARD = "forward"
BACKWARD = "backward"

#: Edges expanded per vertex per hop. Deliberately far below the degree maxima
#: ADR-013 records -- tracing wants the hops nearest in time to the arrival, not
#: a complete neighbourhood.
DEFAULT_DEGREE_CAP = 64

#: Total edges a single trace may collect. Without this the frontier grows as
#: ``degree_cap ** horizon``; at 64 and horizon 4 that is 16.7 million edges.
DEFAULT_EDGE_BUDGET = 10_000


class TraceError(ValueError):
    """Raised when a trace cannot be performed as asked."""


def _epoch_ns(values) -> np.ndarray:
    """Nanoseconds since the epoch, UTC, whatever unit or timezone came in.

    Every time comparison in this module goes through here, because pandas 2
    carries a *resolution* on datetime columns: ``asi8`` yields microseconds on
    one frame and nanoseconds on another, and a scalar ``Timestamp.value`` is
    always nanoseconds. Mixing them scales every comparison by a thousand --
    which is how a forty-day gap reads as under an hour, silently, with the
    traversal still returning plausible-looking edges.
    """
    index = pd.DatetimeIndex(values)
    if index.tz is not None:
        # Convert rather than drop: discarding the zone instead would shift a
        # non-UTC corpus by its offset.
        index = index.tz_convert("UTC").tz_localize(None)
    return index.astype("datetime64[ns]").asi8


@dataclass(frozen=True)
class TraceLimits:
    """Bounds on a single traversal. All three are reported in the result."""

    degree_cap: int = DEFAULT_DEGREE_CAP
    edge_budget: int = DEFAULT_EDGE_BUDGET
    #: Maximum time between arrival and onward movement. Layering moves quickly;
    #: an onward transfer six months later is unlikely to be the same funds.
    #: ``None`` applies no limit, which is the honest default -- a gap threshold
    #: is a policy choice and belongs to the caller.
    max_gap: pd.Timedelta | None = None

    def __post_init__(self) -> None:
        if self.degree_cap < 1:
            raise TraceError("degree_cap must be at least 1")
        if self.edge_budget < 1:
            raise TraceError("edge_budget must be at least 1")


@dataclass
class TraceResult:
    """A time-ordered subgraph reachable from one account."""

    root: str
    direction: str
    horizon: int
    limits: TraceLimits
    edges: pd.DataFrame
    terminals: list[str] = field(default_factory=list)
    capped_vertices: list[str] = field(default_factory=list)
    budget_exhausted: bool = False

    @property
    def n_edges(self) -> int:
        return len(self.edges)

    @property
    def is_complete(self) -> bool:
        """True when no bound bit, so the subgraph is everything reachable.

        A trace that hit a cap is a *sample* of the neighbourhood, not the
        neighbourhood. Anything built on top of a trace must check this before
        describing the result as complete.
        """
        return not self.budget_exhausted and not self.capped_vertices

    def per_hop(self) -> pd.DataFrame:
        """Amounts observed at each depth.

        ``amount`` is the sum of the transactions traced at that depth. It is
        **not** an attribution: once funds enter an account they are commingled
        with its balance, and transaction data alone cannot say which money moved
        on. Treat these as the size of the flow observed at each hop.
        """
        if self.edges.empty:
            return pd.DataFrame(
                columns=["depth", "n_transactions", "n_accounts", "amount"]
            )
        endpoint = (
            S.DESTINATION_ACCOUNT if self.direction == FORWARD else S.SOURCE_ACCOUNT
        )
        grouped = self.edges.groupby("depth")
        return pd.DataFrame(
            {
                "depth": grouped.size().index,
                "n_transactions": grouped.size().to_numpy(),
                "n_accounts": grouped[endpoint].nunique().to_numpy(),
                "amount": grouped[S.AMOUNT].sum().to_numpy(),
            }
        ).reset_index(drop=True)

    def summary(self) -> str:
        head = (
            f"{self.direction} trace from {self.root} | horizon {self.horizon} | "
            f"{self.n_edges:,} transactions, {len(self.terminals):,} terminal accounts"
        )
        if self.is_complete:
            return head + " | complete"
        why = []
        if self.budget_exhausted:
            why.append(f"edge budget {self.limits.edge_budget:,} exhausted")
        if self.capped_vertices:
            why.append(f"{len(self.capped_vertices):,} vertices hit the degree cap")
        return head + " | TRUNCATED: " + "; ".join(why)


class TraceIndex:
    """Time-sorted adjacency over a transaction frame.

    Building this is the expensive step, so it is separated from tracing: one
    index serves many traces. Rather than a dict of arrays per account -- which
    on a five-million-row corpus costs hundreds of megabytes -- edges are sorted
    by ``(account, timestamp)`` once and located with two binary searches.
    """

    def __init__(self, df: pd.DataFrame) -> None:
        missing = {
            S.TRANSACTION_ID,
            S.TIMESTAMP,
            S.SOURCE_ACCOUNT,
            S.DESTINATION_ACCOUNT,
            S.AMOUNT,
        } - set(df.columns)
        if missing:
            raise TraceError(f"frame is missing required columns: {sorted(missing)}")

        self._frame = df

        source = df[S.SOURCE_ACCOUNT].to_numpy()
        destination = df[S.DESTINATION_ACCOUNT].to_numpy()
        # One code space across both endpoints, so a vertex has the same id
        # whether it is sending or receiving.
        self.accounts = pd.Index(pd.unique(np.concatenate([source, destination])))
        self._src_code = self.accounts.get_indexer(source)
        self._dst_code = self.accounts.get_indexer(destination)
        self._time = _epoch_ns(df[S.TIMESTAMP])

        n = len(self.accounts)
        self._out_order, self._out_start, self._out_end = self._build(self._src_code, n)
        self._in_order, self._in_start, self._in_end = self._build(self._dst_code, n)

    def _build(
        self, code: np.ndarray, n_accounts: int
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        order = np.lexsort((self._time, code))
        sorted_code = code[order]
        keys = np.arange(n_accounts)
        start = np.searchsorted(sorted_code, keys, side="left")
        end = np.searchsorted(sorted_code, keys, side="right")
        return order, start, end

    def __len__(self) -> int:
        return len(self._frame)

    @property
    def n_accounts(self) -> int:
        return len(self.accounts)

    def _code(self, account: str) -> int:
        code = self.accounts.get_indexer([account])[0]
        if code < 0:
            raise TraceError(f"account {account!r} does not appear in this frame")
        return int(code)

    def _step(
        self,
        code: int,
        at: int,
        direction: str,
        degree_cap: int,
        max_gap: int | None,
    ) -> tuple[np.ndarray, bool]:
        """Edges leaving (or entering) one vertex, nearest in time to ``at``.

        Returns the row positions and whether the cap truncated them.

        "Nearest in time" rather than "most recent": for a forward trace the
        relevant onward transfers are the ones *soonest after* the funds arrived,
        and for a backward trace the ones *latest before*. Taking the globally
        most recent edges in both directions would, on a forward trace, skip the
        hops that actually follow the money.
        """
        if direction == FORWARD:
            order, lo, hi = self._out_order, self._out_start[code], self._out_end[code]
        else:
            order, lo, hi = self._in_order, self._in_start[code], self._in_end[code]
        if lo == hi:
            return np.empty(0, dtype=np.int64), False

        window = order[lo:hi]
        times = self._time[window]
        if direction == FORWARD:
            first = int(np.searchsorted(times, at, side="left"))
            candidates = window[first:]
            if max_gap is not None:
                keep = int(np.searchsorted(times[first:], at + max_gap, side="right"))
                candidates = candidates[:keep]
            capped = len(candidates) > degree_cap
            return candidates[:degree_cap], capped

        last = int(np.searchsorted(times, at, side="right"))
        candidates = window[:last]
        if max_gap is not None:
            floor = int(np.searchsorted(times[:last], at - max_gap, side="left"))
            candidates = candidates[floor:]
        capped = len(candidates) > degree_cap
        # Latest-before, so take from the tail; the slice stays ascending.
        return (candidates[-degree_cap:] if capped else candidates), capped

    def trace(
        self,
        account: str,
        *,
        direction: str = FORWARD,
        horizon: int = 3,
        at: pd.Timestamp | None = None,
        limits: TraceLimits | None = None,
    ) -> TraceResult:
        """Walk the graph from ``account``, following time.

        ``at`` anchors the walk: a forward trace follows transactions at or after
        it, a backward trace at or before. It defaults to the start of the corpus
        for a forward trace and the end for a backward one, so the default is
        "everything reachable" rather than an arbitrary window.
        """
        if direction not in (FORWARD, BACKWARD):
            raise TraceError(f"direction must be {FORWARD!r} or {BACKWARD!r}")
        if horizon < 1:
            raise TraceError("horizon must be at least 1")
        limits = limits or TraceLimits()

        root_code = self._code(account)
        if at is None:
            anchor = self._time.min() if direction == FORWARD else self._time.max()
        else:
            anchor = int(_epoch_ns([pd.Timestamp(at)])[0])
        max_gap = (
            None
            if limits.max_gap is None
            else int(
                pd.Timedelta(limits.max_gap)
                .to_timedelta64()
                .astype("timedelta64[ns]")
                .astype(np.int64)
            )
        )

        other_code = self._dst_code if direction == FORWARD else self._src_code
        collected: dict[int, int] = {}  # row position -> depth of first arrival
        capped: set[int] = set()
        exhausted = False
        frontier: dict[int, int] = {root_code: int(anchor)}
        reached: set[int] = set()

        for depth in range(1, horizon + 1):
            if exhausted or not frontier:
                break
            nxt: dict[int, int] = {}
            for code, when in frontier.items():
                positions, was_capped = self._step(
                    code, when, direction, limits.degree_cap, max_gap
                )
                if was_capped:
                    capped.add(code)
                for raw in positions:
                    pos = int(raw)
                    if len(collected) >= limits.edge_budget:
                        exhausted = True
                        break
                    collected.setdefault(pos, depth)
                    neighbour = int(other_code[pos])
                    arrival = int(self._time[pos])
                    reached.add(neighbour)
                    # Reaching a vertex earlier (forward) subsumes reaching it
                    # later, so keep the most permissive arrival time and expand
                    # each vertex once per depth.
                    if neighbour in nxt:
                        nxt[neighbour] = (
                            min(nxt[neighbour], arrival)
                            if direction == FORWARD
                            else max(nxt[neighbour], arrival)
                        )
                    else:
                        nxt[neighbour] = arrival
                if exhausted:
                    break
            frontier = nxt

        return self._materialise(
            account, direction, horizon, limits, collected, capped, exhausted, reached
        )

    def _materialise(
        self,
        root: str,
        direction: str,
        horizon: int,
        limits: TraceLimits,
        collected: dict[int, int],
        capped: set[int],
        exhausted: bool,
        reached: set[int],
    ) -> TraceResult:
        columns = [
            S.TRANSACTION_ID,
            S.TIMESTAMP,
            S.SOURCE_ACCOUNT,
            S.DESTINATION_ACCOUNT,
            S.AMOUNT,
        ]
        if not collected:
            empty = self._frame.iloc[:0][columns].copy()
            empty["depth"] = pd.Series(dtype="int64")
            return TraceResult(
                root, direction, horizon, limits, empty, [], [], exhausted
            )

        positions = np.fromiter(collected.keys(), dtype=np.int64, count=len(collected))
        depths = np.fromiter(collected.values(), dtype=np.int64, count=len(collected))
        order = np.lexsort((self._time[positions], depths))
        positions, depths = positions[order], depths[order]

        # Keep the source frame's index. Callers join traced rows back to their
        # features by it -- evidence bundles take per-row SHAP values this way --
        # and renumbering 0..n-1 silently joined them to the wrong rows instead.
        edges = self._frame.iloc[positions][columns].copy()
        edges["depth"] = depths

        # A reached account is terminal when nothing was traced onward from it.
        expanded = set(
            self._src_code[positions]
            if direction == FORWARD
            else self._dst_code[positions]
        )
        terminals = sorted(self.accounts[sorted(reached - expanded)])
        return TraceResult(
            root=root,
            direction=direction,
            horizon=horizon,
            limits=limits,
            edges=edges,
            terminals=list(terminals),
            capped_vertices=sorted(self.accounts[sorted(capped)]),
            budget_exhausted=exhausted,
        )


def trace(
    df: pd.DataFrame,
    account: str,
    *,
    direction: str = FORWARD,
    horizon: int = 3,
    at: pd.Timestamp | None = None,
    limits: TraceLimits | None = None,
) -> TraceResult:
    """Convenience wrapper for a one-off trace.

    Builds an index and discards it. For repeated traces over the same corpus,
    construct a :class:`TraceIndex` once instead -- indexing is the expensive
    part.
    """
    return TraceIndex(df).trace(
        account, direction=direction, horizon=horizon, at=at, limits=limits
    )
