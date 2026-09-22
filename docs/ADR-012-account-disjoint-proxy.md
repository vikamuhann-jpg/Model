# ADR-012 — A weak proxy label needs an account-disjoint partition

> **Note 2026-09-22:** figures in this record were computed with the extractor that inserted
> every edge twice. **Re-run with the corrected extractor** on the same 1.25M-row prefix:
> graph Δ account PR-AUC **+0.0497, 95% CI [0.0186, 0.1079]**, 2,000/2,000 resamples favour
> the graph arm — the result holds. A third arm adding the behaviour features gains a further
> +0.0098 (2σ 0.0085). See [ADR-015](ADR-015-gfp-double-insertion.md) and `experiments/runs/P2_eth*`.

**Status:** Accepted
**Date:** 2026-09-20
**Decision:** When training on a proxy derived from account-level labels, partition the
labelled accounts and let only train-side accounts set a proxy label. Score only
eval-side accounts. A chronological split alone is **not** sufficient.

---

## Context

Tier C asks whether graph structure carries signal on a real network. The corpus is the
XBlock ETH phishing graph, which the capability matrix reports honestly:

```
[yes] account_level_labels       506,613 labelled accounts
[NO ] typology_annotations
[NO ] payment_type
[yes] transaction_level_labels   base rate 0.0000%
```

There is no transaction-level truth. Training a transaction-level model therefore needs
a **weak proxy**: a transaction is *suspicious* if one of its endpoints is a known
phisher. Evaluation stays account-level via S4, so the proxy never enters a reported
metric directly.

## The defect in the first implementation

The first version built the proxy from **every** labelled illicit account in the slice —
including the accounts whose labels define the test metric. The split was chronological,
which felt sufficient because it was sufficient everywhere else in this project.

It is not sufficient here, and the reason is specific to the proxy.

An ETH account persists across the time boundary. A hub labelled illicit contributes
positive proxy rows in the training period and is then scored, from its own labels, in
the test period. The model never sees an account identifier — `schema.feature_view`
forbids it — but **GFP features describe an account's structural position**, and a
persistent hub's structural position is close to an identifier. Memorising "this shape
is illicit" is memorising the account.

The failure is worse than generic leakage because of **which arm it favours**. Row-local
tabular features (amount, hour, currency) barely identify an account. Graph features do.
So the leak inflates T2 over T1 — precisely the contrast Tier C exists to measure. A
contaminated run would have produced a positive transfer result *manufactured by the
contamination*, and it would have looked like the answer we were hoping for.

## Decision

Labelled accounts are partitioned by a stable hash of the account id, 30% to `eval`:

* Only `train`-side illicit accounts may set a proxy label. A transaction touching an
  eval-side phisher is labelled 0 in training — noisy supervision, deliberately, because
  the conservative error is the safe one.
* Only `eval`-side accounts are scored. `evaluate_accounts` receives the eval-side label
  frame.
* The chronological split is unchanged and still applies. Both constraints hold at once.

Hashing rather than shuffling keeps the partition identical across the three seeds, so
the repeats differ only in model initialisation.

## Cost

247 illicit accounts remain usable for training and 119 are held out for evaluation,
against 366 in the slice. Roughly a third of an already small positive set is spent on
making the measurement trustworthy, which reduces power and widens the seed spread.

That is the correct trade. A wide interval around an honest number is a result; a narrow
interval around a contaminated one is not.

## The general rule

**A proxy label inherits the leakage surface of whatever it is derived from.** The
chronological split protects against *temporal* leakage. It does nothing about an entity
that appears on both sides of the boundary carrying the same label — and deriving
training labels from entity-level truth creates exactly that entity.

Any future use of weak or distant supervision in this pipeline must state which entity
the labels attach to and partition on it.

## Revisit if

Transaction-level ground truth becomes available for the target corpus, at which point
the proxy — and this ADR with it — is unnecessary.
