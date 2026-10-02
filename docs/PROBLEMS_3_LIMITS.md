# Problems that cannot be fixed — and what we do instead

**As of 2026-09-26.** These are not tasks. Each is a limit set by the data, the hardware or
the problem itself, and no amount of engineering inside this project removes it. Pretending
otherwise would be the actual failure.

Companion pages: **[PROBLEMS_1_FIXABLE.md](PROBLEMS_1_FIXABLE.md)** (ours to do) ·
**[PROBLEMS_2_BLOCKED.md](PROBLEMS_2_BLOCKED.md)** (waiting on someone else).

**The solution for every item here has the same shape:** measure the limit, state it where
it cannot be missed, and make sure no claim of ours quietly depends on it being smaller than
it is. That is a real deliverable, not a consolation prize — three of these are measurements
a judge cannot obtain from the published benchmark at all.

| | Limit | Set by |
|---|---|---|
| LIM-01 | Blind to every payment rail except ACH | The corpus |
| LIM-02 | The headline is inflated by the generator's tail | The corpus |
| LIM-03 | Low-value laundering is largely missed | The problem |
| LIM-04 | Throughput cannot reach 1,000 tx/s one transaction at a time | The graph |
| LIM-05 | No true off-generator validation is available | The data we have |
| LIM-06 | The full corpus cannot be trained on the VM | The hardware |
| LIM-07 | Two PS9 requirements have no data to build on | The corpus |
| LIM-08 | Laundering with no graph shape is largely missed | The method |

---

## LIM-01 · Blind to every payment rail except ACH
**The limit.** v2's recall at a 1% alert budget is **84.9% on ACH**, **4.2% on cheque**, and
**0% on cash, credit card and Bitcoin**. The cause is the corpus, not the model:
**2,553 of 2,554 injected laundering patterns are on ACH**, and only 144 of 1,797 test
positives are on anything else.

**It is not a HI-Small quirk (measured 2026-09-29).** On a 2M-row LI-Small prefix, 45% of
test laundering is off ACH against HI-Small's 8%, and the shipped model's recall at 1% falls
from 78.3% to **13.3%**. On a corpus where laundering is spread across rails, this limit
is the dominant failure, not a footnote.

**Why no fix exists here.** A supervised model cannot learn a rail it has almost never seen
laundering on. More training, better features and rebalancing all operate on examples that
do not exist. Removing `payment_type` — which we did — stops the model *exploiting* the
artifact; it cannot conjure the missing evidence.

**What we do instead.**
1. **Report recall per rail wherever the headline appears**, so it is never read as a
   general claim. Already in `README.md` and `STATUS.md`.
2. **Treat it as a finding about the benchmark, not only about us.** The published
   comparison uses `payment_type`, and removing that one field halves F1 (ADR-007). That
   half the benchmark's score rests on a simulator convention is worth presenting.
3. **Name what would resolve it:** a corpus whose laundering spans rails — real bank data,
   or a differently configured generator. That is a data acquisition, not a sprint.

## LIM-02 · The headline is inflated by the generator's tail
**The limit.** The test period includes the generator's sparse tail, where laundering runs
at 20–68% of rows (ADR-003). On the dense first window alone — 952k rows, 1,003 positives —
v2's PR-AUC is **0.406**, against **0.595** across the whole test period.

**Why no fix exists here.** The tail is a property of the corpus, and the published protocol
we are compared against includes it. Trimming it would raise our number and make the
comparison dishonest.

**What we do instead.** Publish both, side by side, with the dense-window figure named as
the conservative one — `STATUS.md` does this. When someone asks what this would do on
ordinary traffic, the number to say out loud is **0.41**, not 0.595.

## LIM-03 · Low-value laundering is largely missed
**The limit.** Recall at a 1% budget is **4% below $139** and **34% for $139–599**, against
78% overall.

**Why no fix exists here.** The model's strength is structural — fan-in, fan-out, cycles,
first-time counterparties. A small transfer between two ordinary accounts carries almost no
structural signal, and at a fixed budget it will always rank below one that does. That is a
property of the detection strategy, not a defect in it.

**What we do instead.**
1. **State the amount bands with the headline**, as `README.md` does.
2. **Be clear about the deployment consequence:** this model helps find structured movement
   of significant sums. A bank that needs smurfing detection needs an additional method —
   amount-sequence models, per-account velocity rules.
3. **Accept the trade rather than hide it:** chasing low-value recall at a fixed budget
   costs high-value recall, which is the worse trade for an investigator.

## LIM-04 · Throughput cannot reach 1,000 tx/s one transaction at a time
**The limit.** Gate P8 asks for 1,000 tx/s. Strict one-at-a-time scoring reaches **532
tx/s**. The cost is dominated by degree skew — a few very-high-degree accounts make each
insertion expensive — which we measured and recorded in ADR-013. Periodically rebuilding the
graph yields identical features and buys about 1%.

**Why no fix exists here.** The cost sits inside IBM's graph library and in the shape of the
data, not in our code around it. We measured the alternatives; they do not move it.

**What we do instead — this one is a decision, not a defeat.** Batches of 128 reach **2,785
tx/s** with lookahead inflation below one seed's noise (S1c against S1e), at about 23 seconds
of alert latency on this corpus. So either:
* **adopt micro-batching**, write the ADR, and report P8 as met under a stated latency
  budget; or
* **keep P8 as a reported failure** and let 532 tx/s stand.

What we must not do is quote 2,785 tx/s without the latency it costs. (`PENDING.md` A4 holds
this decision.)

## LIM-05 · No true off-generator validation is available
**The limit.** Everything but one experiment comes from a single IBM generator. Our only
genuinely different network is the XBlock Ethereum phishing graph, where graph features add
**+0.050 account PR-AUC (95% CI 0.019–0.108)** — on a scored set holding just **20 illicit
accounts**. LI-Small, our second corpus, shares the generator and its ACH convention, so it
cannot settle the question ([CORPUS_COMPARISON.md](CORPUS_COMPARISON.md)).

**Why no fix exists here.** No second AML corpus with transaction-level labels is available
to us. The Ethereum result is the strongest off-generator evidence we can obtain, and its
interval is wide because 20 positives is 20 positives.

**What we do instead.**
1. **Claim the direction, not the magnitude.** "Graph features help on a real network, and
   the effect survived our extractor fix unchanged" is supported; a precise number is not.
2. **Keep LI-Small labelled a base-rate contrast**, never external validation, in every
   document that mentions it.
3. **Say what the behaviour features still lack:** validation on one real network with 20
   positives is a first sign, not proof.

## LIM-06 · The full corpus cannot be trained on the VM
**The limit.** The datathon VM has **6 GB of RAM and 2 vCPUs** (s390x, no GPU). The full
corpus is 5,078,345 rows, its feature matrix is about **3.8 GB**, extraction takes hours on
two cores, and training over the whole table peaks at 10.99 GB even on the dev machine.

**Why no fix exists here.** Memory-bounded training helps and is worth doing
([PROBLEMS_1_FIXABLE.md](PROBLEMS_1_FIXABLE.md), COMP-03), but extraction time and file size
remain. A live demo cannot spend hours building features.

**What we do instead.**
1. **Run the notebook on a window** — currently 2 days — and be explicit that it demonstrates
   the pipeline rather than the shipped model.
2. **Reconcile the two numbers wherever they can be seen together.** The gap is the limit;
   the confusion is not, and that part is urgent — written up as BLK-06.
3. **Reproduce the real numbers where the hardware allows**, with `run_validation` on a
   machine that has the memory, and point the notebook at that result.

## LIM-07 · Two PS9 requirements have no data to build on
**The limit.** FR-03 (entity representation: customers, branches, products) and FR-08
(customer, branch and product risk scoring) need fields **no corpus available to us
contains**. Both are marked partial in `PENDING.md` section C.

**Why no fix exists here.** We could invent the entities, but a risk score over fabricated
customers measures nothing, and presenting it would be the one genuinely dishonest thing in
this project.

**What we do instead.**
1. **State the dependency plainly:** these are open by choice, because the corpus has no
   customer dimension.
2. **Show the design that would satisfy them** — the evidence bundle already carries account
   identifiers and traced paths, so customer-level aggregation is a join away once the data
   exists.
3. **Do not claim partial credit** for a requirement we cannot evidence.

## LIM-08 · Laundering with no graph shape is largely missed
**The limit.** Split by whether a laundering transaction belongs to an injected pattern:

| | HI-Small | LI-Small prefix |
|---|---:|---:|
| Structured (patterned) | **95.3%** | 41.2% (7 of 17; ranked 98.7th pct) |
| Unstructured | 27.9% | 9.5% |
| Unstructured, off ACH | 1.4% | 3.1% |
| Share of laundering that is unstructured | 25% | **88%** |

Recall at a 1% alert budget, shipped model. Records: `runs/G1_diagnosis_*.json`.

**Why no fix exists here.** Graph features describe *shape*: who sends to whom, in what
pattern, how fast. A single transfer between two ordinary accounts, with no fan-in, cycle or
chain around it, has no shape to describe. This is a property of the method, not of one
corpus — it holds on both, which is why it is listed here rather than as a transfer bug.

**What we do instead.**
1. **State the scope in the headline**: the model detects laundering that leaves a graph
   shape. `README.md` now opens with that sentence, and with the 95% / 28% split.
2. **Report the composition beside any single number.** A corpus's overall recall is
   mostly its mix: HI-Small is 75% structured and scores 78%; LI-Small is 12% structured and
   scores 13%. Quoting either alone misleads.
3. **Name the remedy as future work, not a patch:** a second detector built on
   account-level behaviour and velocity, combined with the graph score. It is the only
   thing that moves this number, and it is a separate model, not a tweak to this one.

---

## How to present this page

An evaluator will find these limits whether or not we list them. Listing them first is the
difference between a team that understands its model and one that has not looked. Three —
the ACH artifact (LIM-01), the tail (LIM-02), and the latency price of throughput (LIM-04) —
are measurements a judge cannot get from the published benchmark, and they are among the
strongest things we have to say.
