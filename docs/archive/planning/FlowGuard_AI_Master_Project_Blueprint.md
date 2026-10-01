# FlowGuard AI — Master Project Blueprint
## Problem Statement 9: Tracking of Funds within Bank for Fraud Detection

> **Competition positioning:** IBM Z Datathon 2026-ready / enterprise banking fraud & AML prototype  
> **Primary problem:** end-to-end fund-flow tracking, graph analytics, ML-based suspicious-pattern detection, investigator assistance, and evidence generation  
> **Project objective:** maximize the probability of a strong hackathon outcome through direct problem-statement alignment, measurable ML performance, meaningful IBM integration, explainability, and a compelling live demo.
>
> **Important:** No project can honestly guarantee a win. This blueprint is designed to make the project *competitive, technically defensible, demonstrable, and judge-friendly*.

---

# 0. Executive Decision

## Recommended decision

**Choose Problem Statement 9** if your judging criteria strongly reward:

- ML / AI
- fraud detection
- graph analytics
- real-time decisioning
- enterprise architecture
- IBM product integration
- measurable business impact

Do **not** build a generic “transaction fraud dashboard.”

Build:

# **FlowGuard AI**
### Dynamic, Explainable Fund-Flow Intelligence for Fraud Detection

### One-line pitch

> **FlowGuard AI reconstructs the journey of money as a temporal graph, combines graph patterns with customer behaviour and machine learning, identifies suspicious fund-flow typologies, explains why a path is risky, and generates an investigator-ready evidence package.**

---

# 1. Problem Statement

## PS9 — Tracking of Funds within Bank for Fraud Detection

### Context

Money laundering, layering, and fund diversion schemes exploit the complexity of modern banking operations where funds flow through multiple accounts, products, and channels. Traditional transaction monitoring systems focus on individual transactions against static rules, often missing sophisticated schemes that involve multiple hops, round tripping, structuring, or the use of dormant accounts as pass-through vehicles. Regulators increasingly expect banks to demonstrate a holistic understanding of fund flows.

### Description

Develop an intelligent Fund Flow Tracking system that maps and visualises the end-to-end movement of funds within the bank across accounts, products, branches, and channels. The system should use graph analytics and machine learning to identify suspicious fund flow patterns such as rapid layering through multiple accounts, circular transactions (round tripping), structuring below reporting thresholds, sudden activation of dormant accounts for high-value transfers, and mismatches between declared customer profiles and actual fund movement behaviour. The solution should enable investigators to trace the complete journey of funds and generate evidence packages for reporting to the Financial Intelligence Unit (FIU).

---

# 2. Why the Problem Is Important

## 2.1 Regulatory relevance

RBI KYC/AML directions require regulated entities to conduct ongoing due diligence and monitor transactions for patterns inconsistent with the customer's profile, business, risk profile and source of funds. RBI guidance specifically calls for attention to large/complex or unusual transactions, high turnover inconsistent with balances, and money-mule activity; RBI also states that AI/ML may be adopted to support effective monitoring.

Sources:
- RBI Master Direction on KYC / AML: https://www.rbi.org.in/
- RBI KYC amendments and directions: https://www.rbi.org.in/

## 2.2 Indian reporting workload

FIU-IND's FY2024–25 annual-report material reports:

| Metric | FY2023–24 | FY2024–25 |
|---|---:|---:|
| Suspicious Transaction Reports (STRs) | 3,68,592 | **4,34,668** |
| Cross-Border Wire Transfer Reports | 90,87,189 | **1,02,73,512** |
| Priority STRs disseminated to LEAs | 2,750 | **6,908** |

Approximate changes:
- STRs: **+17.9%**
- Cross-border wire reports: **+13.1%**
- Priority STR dissemination: **+151.2%**

Source:
- FIU-IND Publications / Annual Report 2024–25: https://fiuindia.gov.in/files/Publication/Publication.html

## 2.3 Why network-level intelligence matters

BIS Project Aurora states that AML monitoring is often performed in siloed and rules-based ways that can struggle with interconnected, complex fund flows. Its proof of concept combined AI/ML, network analysis and privacy-enhancing technologies. BIS reports that its simulated collaborative approach could detect potentially **up to 3x more complex money-laundering networks** and reduce false positives by **up to 80%** compared with the siloed approach tested.

Sources:
- BIS Project Aurora: https://www.bis.org/project/aurora
- BIS Project Aurora report: https://www.bis.org/publ/othp66.pdf

## 2.4 Why this matters operationally

The goal is not “more alerts.”

The goal is:

> **fewer, better, more explainable cases with a reconstructed fund-flow story.**

---

# 3. Problem Decomposition Using WH Questions

## WHY is the problem happening?

Criminal activity can be distributed across many normal-looking transactions. A suspicious pattern may emerge only when several transactions are viewed together.

## WHAT is missed?

Potentially:
- multi-hop layering
- circular flows / round-tripping
- structuring patterns
- dormant-account activation
- pass-through behaviour
- profile-vs-behaviour mismatches
- connected suspicious accounts

## WHO is affected?

- AML investigators
- fraud teams
- compliance teams
- bank operations
- risk management
- FIU / law-enforcement stakeholders
- legitimate customers affected by unnecessary investigations

## WHEN is detection hardest?

When suspicious activity is:
- distributed across time
- split across channels
- spread across several accounts
- mixed with legitimate transactions
- deliberately made to look normal at the individual-transaction level

## WHERE does the complexity originate?

Across:
- accounts
- customers
- products
- branches
- channels
- devices / sessions where legally and operationally appropriate
- beneficiaries / counterparties

## HOW do criminals exploit the system?

Common patterns include:
- rapid layering
- circular fund movement
- structuring
- dormant-account activation
- money-mule / pass-through accounts
- profile mismatch
- network relationships spanning many accounts

---

# 4. Core Pain Points

## Pain Point 1 — Transaction-level blind spots

A single transaction may look normal while the network is suspicious.

```text
A → B      normal-looking
B → C      normal-looking
C → D      normal-looking
D → E      normal-looking
A → E      suspicious only when combined
```

## Pain Point 2 — False-positive volume

BIS Project Aurora cites estimates that **90–95% of AML alerts may be false positives** in some contexts. Even where exact false-positive rates vary by bank and system, the operational problem is well established.

Source:
https://www.bis.org/publ/othp66.pdf

## Pain Point 3 — Data silos

Customer, account, KYC, transactions, channels, branches, and other signals may exist in different systems. BIS and other financial-sector research highlight fragmentation as a major obstacle to network-level AML analytics.

## Pain Point 4 — Poor investigation context

An alert does not answer:
- where the money originated
- where it went next
- how fast it moved
- which accounts are connected
- whether a cycle exists
- whether behaviour matches the customer profile
- why the model flagged the case

## Pain Point 5 — Slow investigation

Investigators may manually pivot between accounts and transactions.

The desired model is:

```text
Alert
  ↓
One-click fund-flow reconstruction
  ↓
Pattern identification
  ↓
Evidence-backed explanation
```

---

# 5. Existing-Solution Landscape

## 5.1 Traditional rule-based transaction monitoring

### What it does

Static / configurable rules such as:

```text
IF transaction exceeds configured condition
AND customer/account context matches scenario
THEN raise alert
```

### Strengths

- understandable
- auditable
- useful for known scenarios
- easy to validate

### Gaps

- may be narrow
- weak at complex multi-hop relationships
- threshold dependence
- may generate many alerts
- can miss new behavioural patterns

---

## 5.2 Commercial AML suites

Examples include:
- SAS AML
- NICE Actimize
- Quantexa
- other bank-specific AML/fraud platforms

These platforms already offer combinations of:
- transaction monitoring
- ML
- anomaly detection
- entity resolution
- network analytics
- case management
- investigation support
- explainability / prioritisation

### Competitive implication

**Do not claim that graph analytics + ML for AML is new.**

That claim is not defensible.

Instead, FlowGuard's prototype differentiation is:

> **a focused temporal fund-flow intelligence workflow that makes the suspicious path itself the primary object of analysis and produces evidence-backed investigator narratives.**

---

# 6. The Core Opportunity / Solution Gap

## Existing mental model

```text
Transaction
    ↓
Rule / Model
    ↓
Alert
```

## FlowGuard mental model

```text
Transaction
    ↓
Account behaviour
    ↓
Dynamic fund-flow graph
    ↓
Temporal / graph patterns
    ↓
ML anomaly + risk scoring
    ↓
Path-level explanation
    ↓
Investigator case
    ↓
Evidence package
```

### Strategic gap

> **Move from alert-centric monitoring to evidence-backed fund-flow-centric investigation.**

---

# 7. Project Vision

## Vision

Create a bank-wide intelligence layer that can:

1. ingest transaction and customer-context data
2. build a temporal fund-flow graph
3. detect suspicious patterns
4. combine graph analytics with ML
5. rank suspicious paths/cases
6. explain the decision
7. allow investigators to trace funds interactively
8. generate a structured evidence package

---

# 8. Functional Requirements

## FR-01 — Data ingestion

The system shall ingest:
- transaction events
- account data
- customer profile / KYC-derived attributes
- account status
- product information
- branch information
- channel information

The prototype must support CSV/API/stream-like input.

---

## FR-02 — Data normalization

The system shall:
- standardize timestamps
- validate identifiers
- normalize currency/amount fields
- deduplicate events
- validate account relationships
- track data-quality issues

---

## FR-03 — Entity representation

The system shall represent:
- customers
- accounts
- transactions
- products
- branches
- channels
- counterparties

as graph entities or attributes.

---

## FR-04 — Dynamic fund-flow graph

The system shall create edges for:
- transfers
- deposits
- withdrawals
- channel events
- internal account transfers
- other supplied transaction types

Each edge should contain at least:

```text
transaction_id
timestamp
amount
source
destination
channel
product
branch
transaction_type
```

---

## FR-05 — Fund tracing

The investigator shall be able to:
- select an account
- select a transaction
- trace backward
- trace forward
- set hop depth
- set time window
- filter by amount/channel/product

---

## FR-06 — Typology detection

The system shall detect or score:

### Layering
Rapid movement through multiple intermediary accounts.

### Circular flow / round-tripping
Funds return to a prior node/entity in a suspicious cycle.

### Structuring
Behavioural patterns involving fragmented transactions designed to avoid simple monitoring triggers.

### Dormant account activation
Long inactivity followed by abnormal inflow/outflow behaviour.

### Profile mismatch
Observed activity materially deviates from expected customer/account behaviour.

### Pass-through / mule-like behaviour
High inflow followed quickly by high outbound movement with limited retained balance or business rationale indicators.

---

## FR-07 — ML-based anomaly detection

Use:
- supervised model where labels are available
- unsupervised anomaly detector for unknown patterns

Recommended first implementation:
- **XGBoost**
- **Isolation Forest**

Optional:
- Graph Neural Network only if team skill/data/time support it.

---

## FR-08 — Risk scoring

The system shall produce:
- transaction risk
- account behaviour risk
- graph/path risk
- overall case risk

Example:

```text
Transaction risk:     72
Behaviour risk:       84
Graph risk:           93
Profile mismatch:     76
Overall case risk:    91
```

Do not simply average scores without validation.

---

## FR-09 — Explainability

Each high-risk case shall include evidence-linked reasons.

Example:

```text
WHY FLAGGED

1. Account inactive for 11 months
2. ₹18L received in 14 minutes
3. 94% transferred onward within 21 minutes
4. Connected to 6 anomalous accounts
5. Circular path detected
6. Behaviour diverges from declared profile
```

---

## FR-10 — Investigator workflow

Investigator actions:

```text
View case
→ inspect graph
→ inspect timeline
→ inspect supporting transactions
→ view model explanations
→ add notes
→ mark status
→ export evidence
```

---

## FR-11 — Evidence package generation

Generate a structured case bundle:

- case ID
- account/customer identifiers (masked in demo)
- transaction timeline
- graph/path
- suspicious typology
- model scores
- evidence/features
- timestamps
- investigator notes
- audit metadata

For the prototype:

- PDF
- JSON

Do not represent the generated document as an actual FIU filing unless an authorized integration exists.

---

## FR-12 — Real-time / near-real-time scoring

When a transaction arrives:

```text
Event
 ↓
Feature update
 ↓
Risk scoring
 ↓
Graph update
 ↓
Alert / no alert
```

Prototype target:

**sub-second to a few seconds** depending on architecture and demo environment.

---

# 9. Non-Functional Requirements

## NFR-01 — Performance

Target:
- transaction scoring: ideally < 2 seconds in prototype
- graph expansion: ideally < 3 seconds for common queries
- dashboard refresh: < 2 seconds
- case export: < 10 seconds

These are prototype targets, not production guarantees.

---

## NFR-02 — Scalability

Architecture shall separate:
- ingestion
- feature computation
- graph analytics
- ML inference
- UI

so each can scale independently.

---

## NFR-03 — Reliability

Target:
- graceful handling of malformed transactions
- retry / dead-letter pattern for stream inputs
- deterministic risk calculations for identical inputs

---

## NFR-04 — Security

Use:
- synthetic data
- masked identifiers
- role-based access in demo
- least privilege
- encrypted storage/transport where supported
- audit logging
- secret management

---

## NFR-05 — Privacy

Avoid real customer PII.

Use:
```text
Customer_001
Account_78421
TXN_103829
```

Where possible:
- pseudonymize identifiers
- separate sensitive attributes from analytics attributes
- minimize fields used by models

BIS Project Aurora explicitly highlights privacy and data-protection considerations in collaborative AML analytics.

---

## NFR-06 — Explainability

Every material alert should have:
- reason codes
- supporting transactions
- graph/path evidence
- model version
- timestamp

---

## NFR-07 — Auditability

Maintain:
- input-event timestamp
- model version
- feature snapshot/version
- decision output
- investigator actions

---

## NFR-08 — Usability

A judge should understand a high-risk case in **<30 seconds** from the dashboard.

---

# 10. Data Strategy

## 10.1 Data source approach

Use a combination of:

### A. Synthetic banking transactions

Required for controlled fraud patterns.

### B. Public datasets

Where licensing and schema fit.

### C. Synthetic customer/KYC metadata

Needed for:
- profile mismatch
- dormant status
- customer segmentation

### D. Synthetic security/context signals

Only where they add direct value.

---

# 11. Synthetic Data Design

Create a realistic bank-like world:

## Entities

```text
50,000–200,000 accounts
10,000–50,000 customers
1,000–5,000 merchants/businesses
10–100 branches
3–8 channels
```

The exact scale should depend on compute.

## Transaction mix

Mostly normal transactions, with embedded suspicious scenarios.

Example target:

```text
98–99% normal
0.2–1% suspicious/anomalous
```

Do not overbalance the dataset for model convenience.

---

# 12. Ground-Truth Fraud Scenarios

Create injected scenarios with known labels.

## Scenario A — Layering

```text
A → B → C → D → E
```

Properties:
- short inter-transaction intervals
- high pass-through ratio
- multiple hops

---

## Scenario B — Round-tripping

```text
A → B → C → A
```

Properties:
- cycle
- compressed time window
- suspiciously similar amounts

---

## Scenario C — Dormant activation

```text
11 months inactive
        ↓
₹20L inflow
        ↓
₹18.9L onward
```

---

## Scenario D — Structuring

Rather than encode a simplistic legal threshold:

```text
₹X, ₹X, ₹X, ₹X...
```

generate behaviour showing:
- fragmented transfers
- repeated amounts / near-repeated amounts
- compressed timing
- aggregated amount inconsistent with baseline

The system detects suspicious fragmentation; compliance experts make the final determination.

---

## Scenario E — Profile mismatch

Example:

```text
Declared profile:
small local retail business

Observed:
large cross-region flows
high-value transfers
rapid pass-through
```

---

## Scenario F — Fan-in / fan-out

```text
A ─┐
B ─┼→ X → Y
C ─┘
```

or:

```text
X → A
X → B
X → C
X → D
```

---

## Scenario G — Mixed typology

Combine:
- dormant activation
- layering
- cycle
- profile mismatch

This should become the **hero demo case**.

---

# 13. Feature Engineering

## Transaction features

- amount
- time
- channel
- product
- branch
- transaction type
- velocity
- amount deviation

## Account features

- account age
- dormant period
- inbound/outbound ratio
- unique counterparties
- average transaction amount
- transaction count
- balance movement
- velocity

## Graph features

- degree
- weighted degree
- number of neighbours
- path length
- cycle presence
- fan-in
- fan-out
- community/cluster ID
- suspicious-neighbour count

## Temporal features

- time between transactions
- burst frequency
- rolling 5m / 1h / 24h counts
- acceleration of flow
- time from first inflow to final outflow

## Profile features

- expected customer segment
- expected turnover
- expected geography/channel
- observed-vs-expected activity

---

# 14. ML Strategy

## Model 1 — Baseline

**Logistic Regression**

Purpose:
- establish a simple benchmark
- demonstrate why more advanced modelling is required

Metrics:
- precision
- recall
- PR-AUC
- F1

---

## Model 2 — Main supervised model

**XGBoost**

Recommended because:
- handles nonlinear interactions
- works well on tabular data
- strong on mixed banking features
- fast inference
- easy to explain with SHAP

---

## Model 3 — Unknown-pattern detector

**Isolation Forest**

Purpose:
- detect unusual behaviour
- identify previously unseen anomalies
- complement supervised fraud labels

---

## Model 4 — Graph analysis

Start with:

- NetworkX
- connected components
- shortest-path
- cycle detection
- degree / centrality
- subgraph extraction

Optional advanced route:

- graph embeddings
- GraphSAGE
- GAT
- GNN

Only use a GNN if:
- team understands it
- dataset supports it
- it improves measured results

---

# 15. Risk-Scoring Architecture

Use a layered architecture:

```text
                   TRANSACTION
                       │
         ┌─────────────┼─────────────┐
         ↓             ↓             ↓
     Tabular ML     Anomaly       Graph Engine
      XGBoost       Isolation      Patterns
         │             │             │
         └─────────────┼─────────────┘
                       ↓
              Correlation / Risk Layer
                       ↓
                 Overall Case Risk
```

## Example

```text
Transaction Risk       71
Account Anomaly        84
Graph Risk             94
Profile Mismatch       78
Temporal Risk           91
--------------------------
Overall Risk            92
```

The weighting should be learned/calibrated or explicitly justified.

---

# 16. Novelty Strategy

## Do NOT claim

> “We invented graph analytics for AML.”

That is false.

## Do claim

> **“Our innovation is the path-centric, temporal, explainable workflow that links transaction-level ML, account behaviour, and graph typology evidence into one investigator decision.”**

### Differentiators

## 16.1 Path-level risk

Score the **fund journey**, not just the account.

## 16.2 Temporal graph

Use ordering and speed of movement.

## 16.3 Multi-typology correlation

A case can exhibit:

```text
Dormant activation
+
Layering
+
Profile mismatch
```

rather than one isolated label.

## 16.4 Evidence provenance

Each model reason points to actual transactions/graph relationships.

## 16.5 Investigator-first design

The output is a case narrative, not only a model score.

## 16.6 Closed-loop learning

Investigator disposition can become future training feedback.

---

# 17. IBM Integration Strategy

## Principle

**IBM technology must perform a real function.**

Do not put IBM logos only in the architecture slide.

---

## 17.1 IBM Z / LinuxONE

Position IBM Z as the secure enterprise platform for sensitive transactional workloads.

Concept:

```text
Transaction Sources
       ↓
Event / Data Layer
       ↓
IBM Z / LinuxONE
       ↓
Real-Time Analytics
       ↓
AI / Graph
       ↓
Risk Decision
```

The IBM narrative:

> Keep mission-critical banking processing and sensitive financial data close to the system of record, while using AI/analytics for timely risk decisions.

IBM's current Z messaging emphasizes secure, scalable and performant enterprise infrastructure for mission-critical workloads.

---

## 17.2 IBM watsonx.ai

Use for:
- model development
- AI inference
- LLM-based investigator narrative generation
- prompt/model evaluation where appropriate

Important:
**LLM must summarize structured evidence; it should not invent evidence.**

---

## 17.3 IBM watsonx.data

Use for:
- governed transaction data access
- analytical data foundation
- joining transaction/customer/context data
- data lineage

IBM describes watsonx.data as a data foundation for connecting and governing data for AI/analytics.

---

## 17.4 IBM watsonx.governance

Use for:
- model governance
- model metadata
- monitoring
- explainability
- risk documentation
- auditability

---

## 17.5 Streaming / event layer

If the event environment provides IBM-supported streaming/event tooling, use it for:

```text
New transaction
      ↓
Event stream
      ↓
Feature update
      ↓
Risk model
      ↓
Graph update
      ↓
Alert
```

Do not hard-code a product name until the competition environment confirms availability.

---

# 18. IBM Integration Depth Levels

## Level 1 — Weak

```text
Python ML
+
Dashboard
+
IBM logo
```

**Do not do this.**

## Level 2 — Better

```text
watsonx.ai
+
watsonx.data
+
ML pipeline
```

## Level 3 — Strong

```text
IBM Z / LinuxONE
+
watsonx.data
+
watsonx.ai
+
streaming
+
risk engine
```

## Level 4 — Best for prototype

```text
IBM Z / LinuxONE
        ↓
Transaction / event layer
        ↓
watsonx.data
        ↓
Feature + graph analytics
        ↓
watsonx.ai
        ↓
watsonx.governance
        ↓
Investigator decision
```

Use only what the competition environment actually supports.

---

# 19. End-to-End Functional Workflow

```text
STEP 1
Transaction enters bank environment
        ↓
STEP 2
Validate + normalize event
        ↓
STEP 3
Update account behaviour features
        ↓
STEP 4
Update dynamic fund-flow graph
        ↓
STEP 5
Run graph pattern detectors
        ↓
STEP 6
Run ML anomaly / fraud models
        ↓
STEP 7
Compare customer profile vs observed behaviour
        ↓
STEP 8
Correlate temporal + ML + graph signals
        ↓
STEP 9
Calculate risk score
        ↓
STEP 10
Generate evidence-linked explanation
        ↓
STEP 11
Prioritize investigator case
        ↓
STEP 12
Trace money forward/backward
        ↓
STEP 13
Generate evidence package
        ↓
STEP 14
Record investigator disposition
        ↓
STEP 15
Feed validated outcomes back for future model improvement
```

---

# 20. Detailed System Architecture

```text
                         ┌──────────────────────┐
                         │ Transaction Sources  │
                         │ CSV / API / Stream   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Data Validation      │
                         │ & Normalization      │
                         └──────────┬───────────┘
                                    │
                         ┌──────────┴───────────┐
                         │                      │
                         ▼                      ▼
                ┌─────────────────┐    ┌─────────────────┐
                │ Feature Store   │    │ Graph Builder   │
                │ / Analytics     │    │ / Graph DB      │
                └────────┬────────┘    └────────┬────────┘
                         │                      │
                         ▼                      ▼
                ┌─────────────────┐    ┌─────────────────┐
                │ XGBoost         │    │ Graph Analytics │
                │ Isolation Forest│    │ Cycles / Hops   │
                └────────┬────────┘    └────────┬────────┘
                         │                      │
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ Correlation / Risk   │
                         │ Decision Engine      │
                         └──────────┬───────────┘
                                    │
                   ┌────────────────┼────────────────┐
                   ▼                ▼                ▼
             Low risk         Medium risk       High risk
                   │                │                │
                   ▼                ▼                ▼
               Monitor          Review       Investigator Case
                                                     │
                                                     ▼
                                         ┌────────────────────┐
                                         │ Explainable AI     │
                                         │ Evidence Builder   │
                                         └─────────┬──────────┘
                                                   │
                                                   ▼
                                         ┌────────────────────┐
                                         │ Dashboard          │
                                         │ + Fund Trace       │
                                         │ + Report Export    │
                                         └────────────────────┘
```

---

# 21. Investigator Dashboard

## Screen 1 — Risk Overview

```text
Total transactions today:       2,41,839
Alerts generated:                  1,281
High-risk cases:                    117
Cases requiring immediate review:   34
```

---

## Screen 2 — Case Queue

Columns:

```text
Case ID
Risk Score
Typology
Amount
Accounts
Hops
Time Window
Status
```

Example:

```text
FG-1042   93   Layering       ₹48.7L   12   6   47m   OPEN
FG-1038   89   Dormant        ₹18.1L    4   2    9m   REVIEW
FG-1027   86   Round-trip     ₹32.4L    8   4   31m   OPEN
```

---

## Screen 3 — Fund Trace

Interactive graph:

```text
A
│ ₹10L
▼
B
│ ₹9.8L
▼
C
│ ₹9.6L
▼
D
│ ₹9.4L
▼
E
```

Controls:
- 1–6 hops
- time window
- incoming/outgoing
- amount range
- channel
- product

---

## Screen 4 — Why Flagged?

```text
OVERALL RISK: 92/100

Top Evidence

+ 6-hop rapid movement
+ 94% pass-through ratio
+ dormant account activated
+ cycle detected
+ profile mismatch
+ high anomaly score
```

---

## Screen 5 — Timeline

```text
10:31  A → B  ₹10.0L
10:36  B → C   ₹9.8L
10:41  C → D   ₹9.6L
10:47  D → E   ₹9.4L
10:49  E → B   ₹9.2L
```

This makes the pattern visually obvious.

---

# 22. Evidence Package

## Output structure

```text
Case ID
Case creation timestamp
Risk score
Risk category
Primary typology
Secondary typologies
Account/customer identifiers
Transaction IDs
Chronological transaction trail
Fund-flow graph
Supporting features
ML explanations
Graph reasons
Profile mismatch evidence
Investigator notes
Model version
Data snapshot/version
Audit metadata
```

## Sample narrative

> “Account C received ₹18.0 lakh after an 11-month inactivity period and transferred ₹16.9 lakh onward within 21 minutes through three counterparties. The account is connected to a previously anomalous cluster, and the observed velocity and transaction profile materially deviate from its historical baseline.”

The narrative must be generated from structured evidence.

---

# 23. Model Evaluation Strategy

## Do not use accuracy as the headline metric.

Fraud datasets are typically highly imbalanced.

Use:

### Precision
How many flagged cases are truly suspicious?

### Recall
How many suspicious cases did we find?

### F1
Balance precision and recall.

### PR-AUC
Recommended for imbalanced classification.

### False-positive rate / alert reduction
Compare against baseline.

### Detection latency
Time from transaction arrival to risk decision.

### Investigation time
Time from alert creation to understandable fund-flow reconstruction.

### Path reconstruction accuracy
For synthetic cases, what percentage of true suspicious hops are recovered?

### Explanation coverage
Percentage of high-risk cases with evidence-backed explanations.

---

# 24. Baseline Experiment

Create three approaches.

## Baseline A — Rules only

```text
Static rules
```

## Baseline B — ML only

```text
XGBoost on transaction/account features
```

## Proposed C — FlowGuard

```text
ML
+
Anomaly Detection
+
Graph Analytics
+
Temporal correlation
+
Profile mismatch
```

The final presentation should show:

| Metric | Rules | ML | FlowGuard |
|---|---:|---:|---:|
| Precision | X | X | X |
| Recall | X | X | X |
| PR-AUC | X | X | X |
| False positives | X | X | X |
| Detection latency | X | X | X |
| Investigation time | X | X | X |

Fill with measured results only.

---

# 25. Target KPIs for the Prototype

These are **targets**, not guaranteed results.

## ML

- PR-AUC: >0.80 target
- Recall on injected high-risk scenarios: >0.85 target
- Precision: >0.60 target
- Compare against baseline

## Operational

- risk decision: <2 seconds target
- common graph trace: <3 seconds target
- case load: support at least 100k synthetic transactions smoothly

## Investigation

Target:
- reduce time to understand a suspicious path by **50%+** versus a raw-table workflow

## Evidence

Target:
- >95% of high-risk cases contain evidence-linked reason codes

---

# 26. Feasibility Assessment

## Technical feasibility — HIGH

Why:
- graph analytics libraries are mature
- XGBoost and Isolation Forest are accessible
- synthetic data can reproduce target typologies
- dashboard frameworks are fast to build

Primary difficulty:
- designing realistic synthetic transactions
- keeping graph + ML signals consistent
- avoiding leakage in evaluation

---

# 27. Data feasibility — MEDIUM-HIGH

Real bank data will generally not be available.

Therefore:
- use synthetic data
- document generation logic
- validate distributions
- embed known fraud patterns
- keep test cases separate from training data

BIS Project Aurora itself used simulated/synthetic transaction data in its proof-of-concept work, demonstrating that a credible AML research prototype can be built without exposing real customer data.

---

# 28. IBM integration feasibility — MEDIUM-HIGH

It is feasible if the event provides the relevant environment/services.

Risk:
- product availability may vary
- credentials/access may be time-limited
- deployment configuration may consume hackathon time

Mitigation:
- design with a clear abstraction layer
- make the ML core runnable locally
- add IBM services as explicit integration modules
- test connectivity early

---

# 29. Business Viability

## Who would use it?

- AML investigators
- fraud operations
- compliance teams
- financial-crime analytics teams
- enterprise risk teams

## What value is created?

### 1. Better prioritization
Focus analysts on higher-value cases.

### 2. Faster investigation
One-click fund tracing.

### 3. Better explainability
Reason + evidence instead of score alone.

### 4. Better discovery
Find network patterns missed by transaction-only monitoring.

### 5. Better audit readiness
Preserve an evidence trail.

---

# 30. Strategic Fit

## Regulatory fit

Strong.

RBI explicitly requires ongoing monitoring and allows AI/ML to support effective monitoring.

## Banking fit

Very strong.

The challenge is built around actual banking fraud/AML operations.

## AI fit

Very strong.

Uses:
- supervised ML
- unsupervised anomaly detection
- graph analytics
- optional GenAI

## IBM Z fit

Strong when deployed as an enterprise analytical layer close to transactional data and combined with IBM AI/data/governance capabilities.

## Hackathon fit

Strong because it can be demonstrated end-to-end:
- data
- graph
- ML
- detection
- explanation
- investigation
- IBM integration

---

# 31. Strategic Objectives

## Objective 1
Detect complex fraud patterns that are hard to identify from isolated transactions.

## Objective 2
Reduce investigator effort.

## Objective 3
Increase explainability and evidence quality.

## Objective 4
Demonstrate real-time or near-real-time risk intelligence.

## Objective 5
Demonstrate meaningful IBM enterprise integration.

---

# 32. Tactical Plan

## Tactic A — Make graph analytics visible

Do not hide it in the backend.

Show the suspicious path live.

## Tactic B — Combine ML + deterministic graph logic

This improves explainability.

Example:

```text
Graph says:
Cycle = TRUE

ML says:
Behaviour anomaly = 0.91

Profile model says:
Mismatch = HIGH
```

## Tactic C — Use a hero scenario

Build one visually excellent multi-stage case.

## Tactic D — Compare with baseline

Show that your approach improves something measurable.

## Tactic E — Keep the LLM grounded

Only summarize evidence already discovered.

## Tactic F — Make the IBM integration perform a function

Don't create a “Why IBM?” slide without technical substance.

---

# 33. One-Month Preparation Plan

> This is a preparation plan, not permission to violate event rules. The actual competition build must follow the official rules and hacking-window constraints.

## Week 1 — Foundation

### Learn
- AML/fraud typologies
- graph concepts
- XGBoost
- Isolation Forest
- SHAP
- IBM Z / LinuxONE concepts
- watsonx.ai
- watsonx.data
- watsonx.governance

### Deliverables
- problem understanding
- data schema
- architecture
- initial synthetic generator

---

## Week 2 — AI Core

Build:
- baseline rules
- XGBoost
- Isolation Forest
- feature engineering
- evaluation framework

Deliverable:

```text
train.py
evaluate.py
features.py
models/
```

---

## Week 3 — Graph + Product

Build:
- graph construction
- path traversal
- cycle detection
- layering detection
- dashboard
- case view
- timeline

---

## Week 4 — Integration + Pitch

Build/test:
- IBM integration layer
- explainability
- evidence package
- performance testing
- demo script
- architecture diagram
- 2-minute pitch
- 5-minute deep dive

---

# 34. Team Structure

For a 4-member team:

## Member 1 — ML Lead

Responsible for:
- feature engineering
- XGBoost
- anomaly detection
- evaluation

## Member 2 — Graph / Data Engineer

Responsible for:
- graph schema
- graph analytics
- synthetic data
- stream/event processing

## Member 3 — IBM / Backend Lead

Responsible for:
- IBM integration
- APIs
- deployment
- security
- data access

## Member 4 — Frontend / Investigator UX

Responsible for:
- dashboard
- visual fund tracing
- evidence package
- pitch/demo

Everyone should understand the complete architecture.

---

# 35. 24-Hour Datathon Execution Strategy

## Hour 0–2

- understand final challenge
- map to pre-prepared architecture
- define exact MVP
- assign work

## Hour 2–6

- data pipeline
- baseline rules
- transaction graph
- initial model

## Hour 6–12

- ML refinement
- graph typology detectors
- risk engine

## Hour 12–16

- dashboard
- investigator workflow
- evidence package

## Hour 16–20

- IBM integration
- testing
- latency measurement

## Hour 20–22

- final demo scenario
- screenshots
- video
- narrative

## Hour 22–24

- bug fixing
- packaging
- final submission

---

# 36. The Hero Demo

Use a scenario with multiple typologies.

## Step 1

Dormant account activated.

```text
Account C:
Inactive for 11 months
```

## Step 2

Large inflow.

```text
B → C = ₹18L
```

## Step 3

Rapid onward movement.

```text
C → D = ₹16.9L
D → E = ₹16.5L
```

## Step 4

Cycle appears.

```text
E → C
```

## Step 5

Model correlation.

```text
Behaviour risk = 88
Graph risk = 95
Temporal risk = 91
Profile mismatch = 79
```

## Step 6

System outputs.

```text
OVERALL RISK = 94/100
```

## Step 7

Explain.

```text
Possible layering
+
Dormant-account activation
+
Rapid pass-through
+
Circular relationship
+
Profile mismatch
```

## Step 8

Investigator clicks:

> TRACE FUNDS

The graph animates through the path.

## Step 9

Investigator clicks:

> GENERATE EVIDENCE PACKAGE

PDF/JSON appears.

That should be your **hero moment**.

---

# 37. Demo Script

## Opening — 20 seconds

> “A sophisticated financial crime can look normal one transaction at a time. The signal often exists in the journey of the money.”

## Problem — 20 seconds

> “Traditional monitoring can struggle when funds move through multiple accounts and channels. Investigators then have to manually reconstruct the flow.”

## Solution — 30 seconds

> “FlowGuard turns transactions into a temporal graph, combines graph analytics with ML-based behavioural scoring, and reconstructs suspicious fund journeys.”

## Live demo — 2 minutes

Show:
1. transaction arriving
2. graph update
3. risk score
4. suspicious path
5. explanation
6. evidence package

## IBM — 30 seconds

> “The architecture uses IBM enterprise AI/data/governance capabilities and is designed for secure, scalable processing close to mission-critical transaction data on IBM Z/LinuxONE.”

## Results — 30 seconds

Show:
- PR-AUC
- precision
- recall
- false-positive reduction
- investigation-time reduction
- latency

## Close — 10 seconds

> “FlowGuard does not just flag a transaction. It explains the story of the money.”

---

# 38. What Could Make You Lose

## Failure 1 — Generic AML dashboard

Symptom:
- graph
- red/green alerts
- no measured innovation

Fix:
- path-level risk
- temporal logic
- evidence provenance

---

## Failure 2 — Weak ML

Symptom:
- random forest trained on arbitrary features
- no baseline
- no proper evaluation

Fix:
- clear train/test split
- PR-AUC
- recall
- precision
- ablation analysis

---

## Failure 3 — Fake IBM integration

Symptom:

```text
Python app
   +
IBM logo
```

Fix:
- demonstrate real IBM service usage
- show data flow
- show model/deployment integration
- explain why IBM is technically necessary

---

## Failure 4 — LLM hallucination

Symptom:
- LLM invents a fraud explanation

Fix:
- structured evidence layer
- grounded prompt
- source transaction IDs
- deterministic facts

---

## Failure 5 — Over-engineering

Symptom:
- GNN
- LLM
- RAG
- agents
- blockchain
- 10 models

Fix:

> **Do fewer things, but make them work extremely well.**

---

# 39. What Judges Should See in 5 Minutes

A judge should be able to answer “yes” to all:

```text
☑ Is there a real banking problem?
☑ Does the project use ML meaningfully?
☑ Does it detect fraud/AML patterns?
☑ Does it use graph analytics meaningfully?
☑ Can I trace the money?
☑ Can I understand why the case is suspicious?
☑ Is there measurable improvement?
☑ Is IBM genuinely integrated?
☑ Does the solution help an investigator?
☑ Can I imagine a bank using it?
```

---

# 40. Validation / Ablation Experiments

This is an important research-strengthening element.

Compare:

### Model A
Transaction features only

### Model B
Transaction + account behaviour

### Model C
Transaction + account + graph

### Model D
Full FlowGuard

```text
                    PR-AUC
A                   X
B                   X
C                   X
D                   X
```

This demonstrates whether graph and temporal intelligence actually add value.

---

# 41. Data-Leakage Controls

Critical.

Do not allow future transactions to leak into features for past decisions.

For example:

```text
Transaction at 10:00

Features must NOT include:
10:05 transaction
10:07 transaction
```

Use:
- time-based train/test split
- temporal feature cutoff
- separate generated fraud cases

Otherwise your metrics may be artificially inflated.

---

# 42. Model Governance

Track:

```text
Model name
Model version
Training data version
Feature version
Evaluation date
Threshold
Known limitations
```

For every case:

```text
Model version = x.y.z
Risk threshold = T
Inference timestamp = ...
```

This supports auditability.

---

# 43. Responsible AI

## Avoid automated accusations

The system should say:

> **“Potential suspicious pattern detected.”**

not:

> **“Customer is laundering money.”**

The model is decision support.

Human investigators make the final determination.

## Fairness

Evaluate whether model performance differs materially across legitimate customer segments if such data are used.

## Privacy

Use synthetic/pseudonymized data.

---

# 44. Security Design

```text
Authentication
    ↓
Authorization
    ↓
API Gateway
    ↓
Validated Data
    ↓
Analytics
    ↓
Risk Engine
    ↓
Audit Log
```

Protect:
- API credentials
- database credentials
- IBM service tokens
- model artefacts
- sensitive fields

---

# 45. Scalability Design

For the prototype:

```text
Stream
 ↓
Queue
 ↓
Feature service
 ↓
Risk service
 ↓
Graph service
 ↓
Case service
```

Production evolution:

```text
IBM Z / LinuxONE
+
enterprise data layer
+
real-time event processing
+
AI/ML services
+
governance
```

---

# 46. Viability Analysis

## Customer value proposition

> **Reduce investigator time and improve detection of complex fund-flow schemes without replacing existing AML systems.**

## Adoption model

This should be positioned as:

> **intelligence augmentation**

not:

> replacement of the bank's entire AML platform.

## Integration model

Possible integration points:

```text
Existing AML alerts
        ↓
FlowGuard enrichment
        ↓
Fund-flow reconstruction
        ↓
Risk reprioritization
        ↓
Investigator case
```

This is more realistic than asking a bank to replace its entire transaction-monitoring stack.

---

# 47. Commercial Extension

Potential future modules:

### Module 1
Real-time fund-flow risk

### Module 2
Investigator copilot

### Module 3
Cross-account network intelligence

### Module 4
Case management

### Module 5
Model governance

### Module 6
Cross-institution collaborative analytics

BIS Project Aurora is particularly relevant to future cross-institutional AML analytics and privacy-preserving collaboration.

---

# 48. Research / Literature Basis

## Source 1 — RBI

Use for:
- regulatory context
- ongoing due diligence
- suspicious activity
- money mule monitoring
- AI/ML allowance

https://www.rbi.org.in/

## Source 2 — FIU-IND

Use for:
- STR volumes
- reporting workload
- FIU ecosystem

https://fiuindia.gov.in/files/Publication/Publication.html

## Source 3 — BIS Project Aurora

Use for:
- silo limitations
- network analysis
- ML
- false positives
- complex money-laundering detection

https://www.bis.org/project/aurora

## Source 4 — FATF

Use for:
- typologies
- layering
- money-mule activity
- risk-based AML

https://www.fatf-gafi.org/

---

# 49. IBM Reference Strategy

Use official IBM material for:
- IBM Z / LinuxONE
- watsonx.ai
- watsonx.data
- watsonx.governance
- transactional AI
- enterprise AI/security

Suggested starting points:

https://www.ibm.com/z
https://www.ibm.com/products/watsonx-ai
https://www.ibm.com/products/watsonx-data
https://www.ibm.com/products/watsonx-governance

---

# 50. IBM Z Datathon Positioning

The 2026 IBM Z Datathon is a 24-hour global student challenge and IBM's published event material highlights:
- AI for Good
- data-driven innovation
- Real-Time AI for Critical Decisions
- Secure & Privacy-Preserving AI
- a wildcard innovation category
- IBM Z / LinuxONE

Source:
https://community.ibm.com/community/user/events/event-description?CalendarEventKey=0b55f6e4-93a9-4ee4-94ff-019fa8667b04

### Why FlowGuard fits

#### Real-time AI

New transaction → immediate risk decision.

#### Secure / privacy-preserving AI

Sensitive banking data remains controlled and can be pseudonymized.

#### Critical decision

Bank investigators need fast, evidence-backed prioritization.

#### IBM enterprise platform

IBM Z / LinuxONE gives a natural home for mission-critical transaction-oriented workloads.

---

# 51. Scope Control

## MUST HAVE

- transaction ingestion
- synthetic data
- graph construction
- layering detection
- round-trip detection
- dormant activation
- XGBoost
- Isolation Forest
- path risk
- dashboard
- explainability
- evidence package
- at least one real IBM integration

## SHOULD HAVE

- real-time event simulation
- profile mismatch
- SHAP
- case management
- temporal timeline

## NICE TO HAVE

- graph embeddings
- GNN
- LLM investigator copilot
- advanced model governance UI
- federated/privacy-preserving experiment

## DO NOT BUILD UNLESS TIME ALLOWS

- blockchain
- custom LLM training
- full production IAM
- real FIU filing integration
- cross-bank production deployment

---

# 52. Architecture Principle

The project should have **one source of truth for evidence**.

The flow:

```text
Raw transaction
    ↓
Normalized transaction
    ↓
Feature record
    ↓
Graph event
    ↓
Model outputs
    ↓
Evidence object
    ↓
Case
```

Every explanation must trace back to evidence objects.

---

# 53. Evidence Object Design

```json
{
  "case_id": "FG-1042",
  "event_ids": ["TXN-1", "TXN-2", "TXN-3"],
  "risk_score": 94,
  "patterns": [
    "dormant_activation",
    "rapid_layering",
    "cycle"
  ],
  "supporting_features": {
    "pass_through_ratio": 0.94,
    "hop_count": 6,
    "median_inter_event_seconds": 143
  },
  "model_version": "xgb-1.0.0"
}
```

This becomes the source for:
- dashboard
- explanations
- report
- audit trail

---

# 54. Suggested Repository Structure

```text
flowguard-ai/
│
├── README.md
├── docs/
│   ├── problem-statement.md
│   ├── architecture.md
│   ├── research.md
│   ├── requirements.md
│   ├── model-card.md
│   └── demo-script.md
│
├── data/
│   ├── raw/
│   ├── synthetic/
│   ├── features/
│   └── splits/
│
├── data_generation/
│   ├── accounts.py
│   ├── customers.py
│   ├── transactions.py
│   └── fraud_scenarios.py
│
├── features/
│   ├── transaction_features.py
│   ├── account_features.py
│   ├── temporal_features.py
│   └── graph_features.py
│
├── graph/
│   ├── builder.py
│   ├── traversal.py
│   ├── cycles.py
│   ├── layering.py
│   └── scoring.py
│
├── models/
│   ├── baseline.py
│   ├── xgboost_model.py
│   ├── isolation_forest.py
│   └── explainability.py
│
├── risk_engine/
│   ├── correlation.py
│   ├── thresholds.py
│   └── decisions.py
│
├── backend/
│   ├── api.py
│   ├── cases.py
│   └── evidence.py
│
├── frontend/
│   └── dashboard/
│
├── ibm/
│   ├── watsonx_ai/
│   ├── watsonx_data/
│   ├── governance/
│   └── z_integration/
│
├── reports/
│   ├── case_report.py
│   └── templates/
│
└── tests/
    ├── unit/
    ├── integration/
    └── scenario/
```

---

# 55. Testing Strategy

## Unit tests

Test:
- feature calculations
- graph creation
- cycle detection
- dormant activation
- risk calculations

## Integration tests

Test:

```text
transaction
→ graph
→ model
→ risk
→ case
→ evidence
```

## Scenario tests

At minimum:
1. normal
2. layering
3. cycle
4. dormant
5. structuring
6. profile mismatch
7. mixed scenario

---

# 56. Demo Safety

Use synthetic data.

Display:

```text
Customer_1001
Account_7821
```

not:
- real customer names
- real account numbers
- real banking credentials

Do not imply the demo is connected to a production bank.

---

# 57. Decision Threshold Strategy

Use three levels:

```text
0–39   LOW
40–69  MEDIUM
70–100 HIGH
```

These are **demo thresholds**.

In the report, explicitly state:

> Production thresholds require validation against bank-specific risk appetite, historical outcomes, regulatory controls and investigator workflows.

---

# 58. Why Graph + ML, Not Graph OR ML?

## Graph alone

Excellent for:
- cycles
- connectivity
- paths
- community structure

Weakness:
- may not capture all behavioural subtleties

## ML alone

Excellent for:
- feature interactions
- behavioural patterns

Weakness:
- may struggle to explain network topology

## Combined

```text
ML = behaviour intelligence
Graph = relationship intelligence
Rules = known typology control
LLM = evidence summarization
```

This is the central architecture.

---

# 59. Recommended “Innovation Statement”

> **FlowGuard AI treats the movement of funds—not the individual transaction—as the primary analytical object. It builds a temporal graph of money movement, combines network topology with behavioural ML and customer-context mismatch, scores suspicious paths, and converts model findings into evidence-backed investigator cases.**

---

# 60. Recommended Differentiation Statement

> **Existing AML platforms already provide rules, ML, graph analytics and investigation capabilities. Our innovation is not claiming those technologies are new. Instead, the prototype demonstrates a tightly integrated, temporal, path-centric workflow in which every risk score is connected to the exact fund-flow evidence that caused it.**

This statement is more credible than claiming that graph AML is new.

---

# 61. Judge Objection Handling

## Objection:
“Banks already have AML systems.”

### Answer:
> “Yes. We are not claiming to replace them. FlowGuard is an intelligence layer that enriches alerts with temporal fund-flow reconstruction, path-level risk and evidence-backed investigation.”

---

## Objection:
“Why use ML?”

### Answer:
> “Known typologies can be covered by deterministic graph rules, but ML helps discover nonlinear behavioural deviations and prioritize complex cases.”

---

## Objection:
“Why graph analytics?”

### Answer:
> “Because many laundering signals exist in the relationship and sequence among transactions rather than inside one transaction.”

---

## Objection:
“Why IBM Z?”

### Answer:
> “The problem involves sensitive, high-value, mission-critical financial transactions. IBM Z/LinuxONE provides an enterprise-grade environment for secure, scalable processing, while IBM AI/data/governance services can support the analytics lifecycle.”

---

## Objection:
“How do you know the model is good?”

### Answer:
> “We compare against a rule-only baseline and a transaction-only ML baseline using precision, recall, PR-AUC, false-positive rate, latency and investigation-time metrics.”

---

# 62. Competitive Scorecard

Target the following:

| Area | Target |
|---|---|
| Problem relevance | 10/10 |
| AI depth | 9/10 |
| ML rigor | 9/10 |
| Fraud/AML fit | 10/10 |
| Graph intelligence | 10/10 |
| Explainability | 9/10 |
| IBM integration | 9/10 |
| Real-time capability | 8/10 |
| Demo clarity | 10/10 |
| Business value | 9/10 |
| Originality of implementation | 8/10 |

---

# 63. Definition of Done

The project is “competition ready” when all are true:

```text
☑ Data generator works
☑ Normal + suspicious scenarios work
☑ Graph renders correctly
☑ Layering detected
☑ Cycle detected
☑ Dormant activation detected
☑ Profile mismatch detected
☑ XGBoost works
☑ Isolation Forest works
☑ Risk engine works
☑ Explainability works
☑ Fund tracing works
☑ Evidence package works
☑ Dashboard works
☑ IBM integration works
☑ Baseline comparison complete
☑ Metrics documented
☑ Latency measured
☑ Demo can run end-to-end
☑ No real PII used
☑ Limitations documented
```

---

# 64. Final Recommendation

## Project

# **FlowGuard AI**
### Dynamic, Explainable Fund-Flow Intelligence for Fraud Detection

## Core pipeline

```text
TRANSACTION
    ↓
DATA VALIDATION
    ↓
CUSTOMER / ACCOUNT CONTEXT
    ↓
TEMPORAL FUND-FLOW GRAPH
    ↓
GRAPH TYPOLOGY DETECTION
    ↓
ML BEHAVIOURAL ANALYSIS
    ↓
CORRELATION / RISK ENGINE
    ↓
PATH-LEVEL EXPLANATION
    ↓
INVESTIGATOR CASE
    ↓
EVIDENCE PACKAGE
```

## The strongest competition story

> **“Traditional monitoring asks whether this transaction looks suspicious. FlowGuard asks what story the money is telling.”**

---

# 65. Important Strategic Boundaries

Do not:
- integrate the old PayShield network-health concept into PS9
- make UPI-payment reliability the main use case
- claim graph AML is novel
- claim the prototype replaces FIU or bank AML systems
- use real customer financial information
- report unvalidated performance as fact
- force IBM products into irrelevant parts of the architecture

Do:
- keep PS9 as the core
- use ML + graph analytics together
- make the suspicious fund path visible
- make every AI explanation evidence-backed
- compare against clear baselines
- quantify investigator impact
- use meaningful IBM services
- document limitations and governance
- optimize for a complete, polished demo

---

# 66. Master Research References

1. RBI — Master Directions / KYC and AML:
   https://www.rbi.org.in/

2. FIU-IND — Publications and Annual Reports:
   https://fiuindia.gov.in/files/Publication/Publication.html

3. BIS Innovation Hub — Project Aurora:
   https://www.bis.org/project/aurora

4. BIS — Project Aurora report:
   https://www.bis.org/publ/othp66.pdf

5. FATF:
   https://www.fatf-gafi.org/

6. IBM Z:
   https://www.ibm.com/z

7. IBM watsonx.ai:
   https://www.ibm.com/products/watsonx-ai

8. IBM watsonx.data:
   https://www.ibm.com/products/watsonx-data

9. IBM watsonx.governance:
   https://www.ibm.com/products/watsonx-governance

10. IBM Z Datathon 2026 event information:
    https://community.ibm.com/community/user/events/event-description?CalendarEventKey=0b55f6e4-93a9-4ee4-94ff-019fa8667b04

---

# 67. Final Master Principle

## **Do not optimize for “more technology.”**
## **Optimize for “more defensible intelligence per transaction.”**

A winning-quality prototype should make the judge experience:

```text
I see the transaction
        ↓
I see the money move
        ↓
I see the suspicious pattern
        ↓
I see the ML evidence
        ↓
I understand the reason
        ↓
I can investigate it
        ↓
I can export the evidence
        ↓
I understand why IBM Z matters
```

That is the standard this project should be built to meet.
