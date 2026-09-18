"""Hard-negative split (plan v3 section 11 C).

v3 is unambiguous about why this matters: it *"predicts real-world
false-positive pain better than anything else in the framework"*.

The failure mode it targets is a model that has learned **"complex graph =
fraud"**. Plenty of legitimate activity is structurally complex — payroll runs
fan out, treasury sweeps fan in, merchant settlement hubs have enormous degree,
and corporate groups move money in circles for entirely ordinary reasons. A
detector that cannot separate suspicious topology from legitimate complexity
will bury investigators in alerts however good its headline PR-AUC looks.

This module selects structurally complex but **benign** transactions and scores
them as a dedicated slice. Precision there is the number that predicts
operational cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from flowguard.data import schema as S


@dataclass
class HardNegativeSet:
    """Benign transactions selected for structural complexity."""

    index: pd.Index
    reasons: dict[str, int] = field(default_factory=dict)
    account_counts: dict[str, int] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.index)

    def to_metadata(self) -> dict:
        return {
            "n_transactions": len(self.index),
            "selection_reasons": self.reasons,
            "n_accounts_flagged": self.account_counts,
        }

    def evaluate(self, test_df: pd.DataFrame, scores: np.ndarray, budget: float) -> dict:
        """False-positive rate on this slice at a given alert budget.

        The alert threshold is taken from the **full** test set, not from the
        slice: the question is how many of these benign-but-complex rows would
        be alerted by a system operating at that budget.
        """
        scores = np.asarray(scores, dtype=float)
        n = len(scores)
        k = max(1, int(round(n * budget)))
        cutoff = np.partition(scores, -k)[-k]

        positions = test_df.index.get_indexer(self.index)
        positions = positions[positions >= 0]
        if len(positions) == 0:
            return {"n": 0}

        slice_scores = scores[positions]
        flagged = int((slice_scores >= cutoff).sum())

        # Compare against ordinary benign rows to see whether complexity alone
        # is what drives the alerts.
        benign = (test_df[S.IS_LAUNDERING].to_numpy() == 0)
        benign_flagged = int((scores[benign] >= cutoff).sum())
        benign_rate = benign_flagged / max(1, benign.sum())
        hard_rate = flagged / len(positions)

        return {
            "n": len(positions),
            "budget": budget,
            "flagged": flagged,
            "false_positive_rate": hard_rate,
            "baseline_benign_rate": benign_rate,
            # >1 means complex-but-legitimate activity is alerted more often
            # than ordinary legitimate activity.
            "enrichment_vs_ordinary_benign": (
                hard_rate / benign_rate if benign_rate else float("nan")
            ),
        }


def select_hard_negatives(
    df: pd.DataFrame,
    *,
    fan_quantile: float = 0.99,
    volume_quantile: float = 0.99,
    min_counterparties: int = 5,
    min_reciprocal: int = 3,
) -> HardNegativeSet:
    """Pick benign transactions belonging to structurally complex accounts.

    Three families, all computed on the partition passed in:

    * **high fan-out with regular cadence** — payroll-like: many distinct
      destinations, low variance in inter-transaction gaps.
    * **high-volume hubs** — merchant settlement-like: extreme degree.
    * **reciprocal pairs** — two accounts transacting in both directions, the
      simplest legitimate structure that looks like a cycle.
    """
    benign = df[df[S.IS_LAUNDERING] == 0]
    if benign.empty:
        return HardNegativeSet(index=pd.Index([]))

    out_deg = benign.groupby(S.SOURCE_ACCOUNT, observed=True)[
        S.DESTINATION_ACCOUNT
    ].nunique()
    in_deg = benign.groupby(S.DESTINATION_ACCOUNT, observed=True)[
        S.SOURCE_ACCOUNT
    ].nunique()
    sent = benign.groupby(S.SOURCE_ACCOUNT, observed=True).size()

    fan_cut = max(min_counterparties, float(out_deg.quantile(fan_quantile)))
    in_cut = max(min_counterparties, float(in_deg.quantile(volume_quantile)))
    vol_cut = float(sent.quantile(volume_quantile))

    fan_out_accounts = set(out_deg[out_deg >= fan_cut].index)
    fan_in_accounts = set(in_deg[in_deg >= in_cut].index)
    hub_accounts = set(sent[sent >= vol_cut].index)

    # Regular cadence: low coefficient of variation in inter-transaction gaps.
    cadence_accounts: set[str] = set()
    candidates = benign[benign[S.SOURCE_ACCOUNT].isin(fan_out_accounts)]
    for account, group in candidates.groupby(S.SOURCE_ACCOUNT, observed=True):
        if len(group) < 4:
            continue
        gaps = group[S.TIMESTAMP].sort_values().diff().dropna()
        seconds = gaps.dt.total_seconds().to_numpy()
        if len(seconds) < 3 or seconds.mean() == 0:
            continue
        if seconds.std() / seconds.mean() < 0.5:  # regular, payroll-like
            cadence_accounts.add(account)

    # Reciprocal pairs: A->B and B->A, and *sustained* in both directions.
    # A single exchange each way is a coincidence, not a relationship -- on a
    # dense graph almost every pair is reciprocal by chance, which would select
    # the entire benign population and make the slice meaningless.
    pair_counts = (
        benign.groupby([S.SOURCE_ACCOUNT, S.DESTINATION_ACCOUNT], observed=True)
        .size()
        .to_dict()
    )
    reciprocal: set[str] = set()
    for (a, b), count in pair_counts.items():
        back = pair_counts.get((b, a), 0)
        if count >= min_reciprocal and back >= min_reciprocal:
            reciprocal.add(a)

    selected = pd.Series(False, index=benign.index)
    reasons: dict[str, int] = {}

    for name, accounts, column in (
        ("high_fan_out", fan_out_accounts, S.SOURCE_ACCOUNT),
        ("high_fan_in", fan_in_accounts, S.DESTINATION_ACCOUNT),
        ("high_volume_hub", hub_accounts, S.SOURCE_ACCOUNT),
        ("regular_cadence_fan_out", cadence_accounts, S.SOURCE_ACCOUNT),
        ("reciprocal_pair", reciprocal, S.SOURCE_ACCOUNT),
    ):
        mask = benign[column].isin(accounts)
        reasons[name] = int(mask.sum())
        selected |= mask

    index = benign.index[selected.to_numpy()]
    share = len(index) / len(benign) if len(benign) else 0.0
    if share > 0.5:
        import warnings

        warnings.warn(
            f"hard-negative slice covers {share:.0%} of benign rows; a slice "
            "that large is the population, not a hard subset -- tighten the "
            "quantiles or min_reciprocal.",
            stacklevel=2,
        )

    return HardNegativeSet(
        index=index,
        reasons=reasons | {"share_of_benign": round(share, 4)},
        account_counts={
            "high_fan_out": len(fan_out_accounts),
            "high_fan_in": len(fan_in_accounts),
            "high_volume_hub": len(hub_accounts),
            "regular_cadence_fan_out": len(cadence_accounts),
            "reciprocal_pair": len(reciprocal),
        },
    )
