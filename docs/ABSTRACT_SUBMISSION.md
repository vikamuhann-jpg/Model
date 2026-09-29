# FlowGuard — Abstract Submission

Structure follows the abstract template in the University of Memphis *Step-by-Step Guide to
Hackathon Abstract and Pitch Creation* (2025): Problem Statement → Background → Objective →
Solution → Impact, **500 words max**. Stage 1 submission: the idea and approach only,
no model metrics — those live in [`STATUS.md`](STATUS.md) for later stages.

---

## Submission details

| Field | Entry |
|---|---|
| **Title** | FlowGuard: Explainable, Lookahead-Free Fund-Flow Intelligence for AML Detection |
| **Problem statement** | PS9 — Tracking of Funds within Bank for Fraud Detection |
| **Team name** | _[fill in]_ |
| **Team members** | _[fill in — name, institution, email]_ |
| **Domain** | Financial crime / anti-money laundering · graph machine learning |
| **Platform** | IBM LinuxONE (s390x) · IBM Snap ML Graph Feature Preprocessor · XGBoost |
| **Keywords** | money laundering, fund tracing, temporal transaction graph, graph features, explainable AI, XGBoost |

---

## Abstract

**Problem Statement.** Money laundering hides in the journey, not the transaction: each
transfer in a layering chain, cycle or fan-out can look ordinary while the path it belongs
to is not. Transaction-centric rules miss these patterns and still bury investigators in
alerts — BIS Project Aurora cites false-positive rates of 90–95% in some contexts. Banks
need to see where funds went and why a movement is suspicious.

**Background.** Graph analytics with machine learning is established for AML. IBM's Graph
Feature Preprocessor (GFP) with XGBoost is the published benchmark on the IBM AML dataset.
Reproducing it, we found the score rests on two things a bank cannot use: a simulator
artifact — almost every injected laundering pattern sits on one payment rail — and batched
scoring that lets a transaction see later ones. The gap is a detector whose accuracy survives without both, and that explains
itself to an investigator.

**Objective.** Build a transaction-risk model that (1) scores strictly one transaction at a
time, with no lookahead and no payment-rail field; (2) matches the published benchmark on
its own protocol — full corpus, chronological 60/20/20 split, five seeds; (3) names every
alert's reasons in plain language; and (4) traces funds forward and backward in time.

**Solution.** FlowGuard streams transactions through Snap ML's GFP to compute graph-pattern
features — fan-in, fan-out, cycles, scatter-gather — and adds ten strictly causal
account-behaviour features drawn from AML red flags: first-time counterparty, dormant
account suddenly sending, funds passed straight through. A calibrated XGBoost model ranks
transactions against a stated alert budget. Each alert becomes an evidence bundle: the
time-ordered fund trace, the transactions on it, named reasons from TreeSHAP attributions,
the model version and threshold provenance; the bundle checks its own consistency. A
merge-blocking leakage test suite and sixteen decision records back every number.

**Impact.** FlowGuard shows that graph structure combined with account behaviour can carry
AML detection without the simulator's artifact and without lookahead — conditions a real
bank actually operates under. A check on a real network, the Ethereum phishing graph,
indicates the graph signal is not specific to synthetic data. Investigators get a ranked
queue with a traceable story for every alert instead of a bare score, and every limitation
found along the way is stated rather than hidden. The pipeline runs within the datathon's
IBM LinuxONE environment using only its pre-installed packages.

---

## Pre-submission checklist

- [ ] Abstract is under 500 words (Problem Statement through Impact)
- [ ] Team name and members filled in
- [ ] No model metrics in the text (stage 1)
- [ ] Objectives and metrics clearly defined
- [ ] Slides or visuals prepared for the pitch (3–5 minutes)
