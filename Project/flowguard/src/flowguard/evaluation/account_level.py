"""Account-level evaluation, for corpora that label accounts rather than
transactions (Tier S4).

The IBM AML corpora label **transactions**. ETH Phishing labels **accounts**.
Every metric in this project assumes the former, so cross-dataset validation
needs a second evaluation path rather than a coercion of one into the other.

Why label propagation is rejected
---------------------------------
The tempting shortcut is to mark every transaction touching a flagged account as
positive. It is wrong, and wrong in a way that produces a plausible-looking
number:

* A phishing account also **receives legitimate funds** from victims who are not
  themselves illicit. Propagation labels those transactions positive.
* It inflates the positive class by the account's entire transaction volume, so
  the base rate stops meaning anything.
* Precision becomes uninterpretable: a model that flags every transaction of one
  busy flagged account scores well while having detected one account.

So propagation is not offered as an option here. Scores are aggregated **up** to
the account instead, and compared against the label the dataset actually
provides.

What this does and does not license
-----------------------------------
A transaction-level result and an account-level result answer different
questions -- *"is this transaction part of laundering?"* versus *"is this
account a phisher?"*. They are **not like-for-like** and must never be reported
as a single comparable number. The legitimate cross-dataset claim is narrower
and more interesting: does **graph structure carry signal in both settings**?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.evaluation.metrics import DEFAULT_BUDGETS, Metrics, evaluate

Aggregation = Literal["max", "mean", "topk_mean"]

#: `max` is primary: detection is a screening problem, and one clearly
#: suspicious transaction should be enough to surface an account. The others are
#: reported alongside so the choice is visible rather than buried.
PRIMARY_AGGREGATION: Aggregation = "max"

DEFAULT_TOP_K = 3


class AccountLevelError(ValueError):
    """Raised when account-level evaluation cannot be performed honestly."""


@dataclass
class AccountScores:
    """Per-account scores aggregated from transaction scores."""

    account_id: np.ndarray
    score: np.ndarray
    n_transactions: np.ndarray
    aggregation: Aggregation

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "account_id": self.account_id,
                "score": self.score,
                "n_transactions": self.n_transactions,
            }
        )


def aggregate_to_accounts(
    df: pd.DataFrame,
    scores: np.ndarray,
    *,
    aggregation: Aggregation = PRIMARY_AGGREGATION,
    top_k: int = DEFAULT_TOP_K,
    endpoints: tuple[str, str] = (S.SOURCE_ACCOUNT, S.DESTINATION_ACCOUNT),
) -> AccountScores:
    """Roll transaction scores up to the accounts involved.

    An account inherits the scores of every transaction it participates in, on
    either side. A pass-through account is implicated by the transactions it
    forwards as much as by those it receives, and restricting to one side would
    make the aggregation direction-dependent for no principled reason.
    """
    scores = np.asarray(scores, dtype=float)
    if len(scores) != len(df):
        raise AccountLevelError(
            f"length mismatch: {len(df)} transactions, {len(scores)} scores"
        )

    long = pd.concat(
        [
            pd.DataFrame({"account_id": df[col].to_numpy(), "score": scores})
            for col in endpoints
        ],
        ignore_index=True,
    )

    grouped = long.groupby("account_id", observed=True)["score"]
    if aggregation == "max":
        agg = grouped.max()
    elif aggregation == "mean":
        agg = grouped.mean()
    elif aggregation == "topk_mean":
        agg = grouped.apply(lambda s: s.nlargest(min(top_k, len(s))).mean())
    else:  # pragma: no cover - guarded by the Literal
        raise AccountLevelError(f"unknown aggregation: {aggregation}")

    counts = grouped.size()
    return AccountScores(
        account_id=agg.index.to_numpy(),
        score=agg.to_numpy(),
        n_transactions=counts.reindex(agg.index).to_numpy(),
        aggregation=aggregation,
    )


@dataclass
class AccountEvaluation:
    """Account-level metrics, with every aggregation reported."""

    primary: Metrics
    by_aggregation: dict[str, Metrics] = field(default_factory=dict)
    n_accounts: int = 0
    n_labelled: int = 0
    n_positive: int = 0
    unlabelled_policy: str = ""

    def to_metadata(self) -> dict:
        return {
            "unit": "account",
            "primary_aggregation": PRIMARY_AGGREGATION,
            "n_accounts": self.n_accounts,
            "n_labelled": self.n_labelled,
            "n_positive": self.n_positive,
            "unlabelled_policy": self.unlabelled_policy,
            "primary": self.primary.to_metadata(),
            "by_aggregation": {
                k: v.to_metadata() for k, v in self.by_aggregation.items()
            },
            "comparability": (
                "NOT comparable to transaction-level PR-AUC -- a different "
                "question is being asked. Report side by side, never as one "
                "number."
            ),
        }

    def summary(self) -> str:
        lines = [
            f"account-level evaluation ({self.n_labelled:,} labelled accounts, "
            f"{self.n_positive:,} positive)",
            f"  policy for unlabelled accounts: {self.unlabelled_policy}",
        ]
        for name, metrics in self.by_aggregation.items():
            marker = " (primary)" if name == PRIMARY_AGGREGATION else ""
            lines.append(
                f"  {name + marker:20s} PR-AUC={metrics.pr_auc:.4f} "
                f"lift={metrics.lift:.1f}x"
            )
        return "\n".join(lines)


def evaluate_accounts(
    df: pd.DataFrame,
    scores: np.ndarray,
    account_labels: pd.DataFrame,
    *,
    id_column: str = "account_id",
    label_column: str = "is_illicit",
    budgets: tuple[float, ...] = DEFAULT_BUDGETS,
    top_k: int = DEFAULT_TOP_K,
) -> AccountEvaluation:
    """Score accounts from transaction scores and evaluate against node labels.

    Accounts with no label are **excluded**, not treated as negatives. In a
    partially-labelled network — which is what public illicit-address datasets
    are — an unlabelled account is unknown, and scoring it as benign would
    manufacture false positives out of missing data. The count of excluded
    accounts is reported so the coverage is visible.
    """
    if id_column not in account_labels.columns:
        raise AccountLevelError(f"account_labels lacks {id_column!r}")
    if label_column not in account_labels.columns:
        raise AccountLevelError(f"account_labels lacks {label_column!r}")

    results: dict[str, Metrics] = {}
    n_accounts = n_labelled = n_positive = 0

    labels = account_labels[[id_column, label_column]].drop_duplicates(id_column)

    for aggregation in ("max", "mean", "topk_mean"):
        agg = aggregate_to_accounts(
            df, scores, aggregation=aggregation, top_k=top_k  # type: ignore[arg-type]
        )
        frame = agg.to_frame().merge(
            labels, left_on="account_id", right_on=id_column, how="inner"
        )
        n_accounts = len(agg.account_id)
        n_labelled = len(frame)
        if n_labelled == 0:
            raise AccountLevelError(
                "no account in the transaction set matched a label; check that "
                "account identifiers use the same convention on both sides"
            )
        y = frame[label_column].to_numpy().astype(int)
        n_positive = int(y.sum())
        results[aggregation] = evaluate(y, frame["score"].to_numpy(), budgets=budgets)

    return AccountEvaluation(
        primary=results[PRIMARY_AGGREGATION],
        by_aggregation=results,
        n_accounts=n_accounts,
        n_labelled=n_labelled,
        n_positive=n_positive,
        unlabelled_policy=(
            f"excluded ({n_accounts - n_labelled:,} of {n_accounts:,} accounts "
            "carry no label and are treated as unknown, not benign)"
        ),
    )
