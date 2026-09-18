# FlowGuard AI — PS9 Quick Project Brief

## 1. Problem Statement

### PS9 — Tracking of Funds within Bank for Fraud Detection

Banks need to understand the **complete journey of funds**, not just individual transactions.

The problem statement asks for an intelligent system that:

- maps and visualizes movement of funds across **accounts, products, branches and channels**
- uses **graph analytics + machine learning**
- detects suspicious patterns such as:
  - layering / rapid multi-hop movement
  - round-tripping / circular transactions
  - structuring-like fragmented behaviour
  - dormant-account activation followed by unusual transfers
  - mismatch between customer profile and actual fund movement
- helps investigators **trace the complete fund journey**
- generates **FIU-oriented evidence packages**

### Core idea

> **Move from transaction-level alerts to explainable fund-flow intelligence.**

---

# 2. Why This Problem Matters

## Business / regulatory relevance

RBI requires ongoing monitoring of customer transactions against customer profile, business/risk profile and source of funds, and its KYC/AML directions allow use of AI/ML for effective monitoring and address money-mule activity.

FIU-IND FY2024–25 figures reported in the research document include:

| Metric | FY2024–25 |
|---|---:|
| Suspicious Transaction Reports (STRs) | **4,34,668** |
| Cross-Border Wire Transfer Reports | **1,02,73,512** |
| Priority STRs disseminated to LEAs | **6,908** |

BIS Project Aurora also highlights the value of combining **AI/ML, network analysis and privacy-preserving approaches** for complex AML detection.

### Main implication

The challenge is not simply:

> “Find suspicious transactions.”

It is:

> **“Filter, connect, prioritize and investigate large volumes of financial activity to understand the story of the money.”**

---

# 3. Pain Points

## Why?

Criminals can split activity across many transactions/accounts so that each individual transaction appears normal while the combined network is suspicious.

## What gets missed?

- multi-hop layering
- circular / round-trip flows
- fragmented suspicious activity
- dormant accounts used as pass-through accounts
- profile-vs-behaviour mismatch
- connected suspicious accounts

## Who suffers?

- AML investigators
- fraud/compliance teams
- banks
- law-enforcement/FIU stakeholders
- legitimate customers affected by unnecessary alerts

## When is detection hardest?

When suspicious activity is spread across:

- multiple transactions
- multiple accounts
- multiple channels
- time
- different branches/products

## Where is the complexity?

```text
Customer
   ↓
Account
   ↓
Product
   ↓
Channel
   ↓
Branch / Counterparty
   ↓
Other Account
```

## How do existing approaches struggle?

### 1. Transaction-centric monitoring
A single transaction may look normal while the entire path is suspicious.

### 2. False positives
Very high false-positive volumes are a known AML challenge; BIS Project Aurora cites 90–95% estimates in some contexts.

### 3. Data silos
Transaction, KYC, customer and channel context can be fragmented across systems.

### 4. Investigation effort
Investigators need the **path, timeline, relationships and reasons**, not just an alert.

---

# 4. Existing Solutions

## Traditional rule-based monitoring

**Strengths**
- simple
- auditable
- useful for known patterns

**Gaps**
- static/narrow
- weak at complex network relationships
- can generate many alerts
- limited for emerging typologies

## Commercial AML platforms

Examples:
- SAS AML
- NICE Actimize
- Quantexa
- bank-specific AML systems

These already use combinations of:
- rules
- ML
- anomaly detection
- graph/network analytics
- entity resolution
- case management

### Important conclusion

> **Do NOT claim that graph analytics + ML for AML is new.**

The project must differentiate through the **workflow and measurable outcome**, not by claiming ownership of existing technologies.

---

# 5. Our Solution

# FlowGuard AI

### Dynamic, Explainable Fund-Flow Intelligence for Fraud Detection

## Key differentiator

> **Make the suspicious fund journey the primary object of analysis.**

Instead of:

```text
Transaction → Alert
```

FlowGuard does:

```text
Transaction
   ↓
Account behaviour
   ↓
Temporal fund-flow graph
   ↓
Graph patterns
   ↓
ML/anomaly analysis
   ↓
Customer-profile context
   ↓
Path-level risk
   ↓
Evidence-backed investigation
```

---

# 6. End-to-End Workflow

## Step 1 — Ingest data

Inputs:

- transactions
- accounts
- customers
- KYC/profile attributes
- account status
- products
- branches
- channels

---

## Step 2 — Build behavioural baselines

For each account, calculate:

- normal transaction count
- average amount
- velocity
- typical counterparties
- typical channels
- normal time windows
- dormancy period
- inflow/outflow ratio

---

## Step 3 — Build a temporal fund-flow graph

### Nodes

- customer
- account
- merchant/business
- branch
- product

### Edges

- transfers
- deposits
- withdrawals
- UPI
- NEFT
- RTGS
- IMPS
- internal transfers

Example:

```text
A ──₹10L──> B ──₹9.7L──> C ──₹9.4L──> D
```

Each edge should retain:

- transaction ID
- timestamp
- amount
- source
- destination
- channel
- product
- branch
- transaction type

---

## Step 4 — Detect graph patterns

### Layering
```text
A → B → C → D → E
```

### Round-tripping
```text
A → B → C → A
```

### Fan-in
```text
A ─┐
B ─┼→ X
C ─┘
```

### Fan-out
```text
      B
     ↗
A → C
     ↘
      D
```

### Dormant-account activation
```text
Long inactivity
      ↓
Large inflow
      ↓
Rapid outward transfers
```

### Profile mismatch
Actual transaction behaviour materially differs from expected customer/account behaviour.

> Do not equate a single threshold breach with “fraud” or “structuring.” The system identifies suspicious behavioural patterns; final regulatory determination remains human/institutional.

---

# 7. ML Strategy

## Model 1 — Baseline
**Logistic Regression**

Purpose:
- simple benchmark
- compare against advanced approaches

## Model 2 — Main supervised model
**XGBoost**

Use for:
- transaction/account risk
- nonlinear behaviour patterns

## Model 3 — Unsupervised anomaly detection
**Isolation Forest**

Use for:
- unusual behaviour
- unknown patterns

## Graph layer
Start with:
- NetworkX
- cycle detection
- path analysis
- degree/centrality
- fan-in/fan-out
- temporal graph features

### Optional

Use GNN/GraphSAGE only if:
- the team can support it
- the data supports it
- it improves measured results

---

# 8. Risk Engine

Combine:

```text
Transaction Risk
+
Behaviour Risk
+
Graph Risk
+
Temporal Risk
+
Profile Mismatch
        ↓
Overall Fund-Flow Risk
```

Example:

```text
Transaction anomaly   73
Behaviour anomaly     88
Graph anomaly         94
Temporal risk         91
Profile mismatch      79

Overall risk          93/100
```

The production weighting should be validated; do not simply average scores without justification.

---

# 9. Explainability

Every important alert should answer:

> **Why was this flagged?**

Example:

```text
WHY FLAGGED

1. Account inactive for 11 months
2. ₹18L received within 14 minutes
3. 94% transferred onward within 21 minutes
4. Connected to 6 anomalous accounts
5. Circular path detected
6. Behaviour differs from customer baseline
```

The explanation must be linked to **actual evidence**, not invented by an LLM.

---

# 10. Investigator Experience

## Dashboard should show

### Case overview

```text
Case: FG-1042
Risk: 93/100
Pattern: POSSIBLE LAYERING
Amount: ₹48.7L
Accounts: 12
Hops: 6
Time window: 47 min
```

### Fund trace

```text
A → B → C → D → E → F
```

Investigator can:
- trace backward
- trace forward
- set hop depth
- filter by time
- filter by amount/channel/product

### Timeline

```text
10:31 A → B ₹10L
10:36 B → C ₹9.8L
10:41 C → D ₹9.6L
10:47 D → E ₹9.4L
```

---

# 11. Evidence Package

Generate an **FIU-oriented investigation-support package**, not an actual FIU submission.

Include:

- case ID
- masked account/customer identifiers
- transaction timeline
- suspicious graph/path
- detected typologies
- risk scores
- supporting evidence/features
- transaction IDs
- timestamps
- investigator notes
- model version
- audit metadata

Formats for prototype:
- PDF
- JSON

---

# 12. Metrics That Matter

Do NOT headline:

> “95% accuracy.”

Fraud data is usually imbalanced.

Measure:

### ML
- Precision
- Recall
- F1
- PR-AUC

### Operational
- false-positive reduction
- detection latency
- graph-trace response time

### Investigation
- time to understand a case
- time to reconstruct a fund path

### Coverage
- fund-trace completeness
- percentage of alerts with evidence-backed explanations

---

# 13. Best Experimental Design

Compare three approaches:

### A — Rules only

```text
Static rules
```

### B — ML only

```text
XGBoost on transaction/account features
```

### C — FlowGuard

```text
ML
+
Anomaly Detection
+
Graph Analytics
+
Temporal Correlation
+
Profile Context
```

Report measured differences:

| Metric | Rules | ML | FlowGuard |
|---|---:|---:|---:|
| Precision | X | X | X |
| Recall | X | X | X |
| PR-AUC | X | X | X |
| False positives | X | X | X |
| Detection latency | X | X | X |
| Investigation time | X | X | X |

Use real experimental results only.

---

# 14. Novelty / Uniqueness

## What is NOT novel

- AML transaction monitoring
- graph analytics
- ML fraud detection
- anomaly detection
- investigator dashboards

## What we should differentiate

### 1. Path-level risk
Score the **whole fund journey**, not only accounts/transactions.

### 2. Temporal graph
Use sequence and speed of movement.

### 3. Multi-typology correlation
One case may contain:
```text
Dormant activation
+
Layering
+
Profile mismatch
```

### 4. Evidence provenance
Every risk explanation points to supporting transactions/graph evidence.

### 5. Investigator-first workflow
The output is a traceable case narrative, not just a score.

---

# 15. IBM Integration

The IBM layer must perform real functions.

## IBM Z / LinuxONE
Use as the enterprise platform concept for:
- sensitive financial workloads
- secure processing
- scalable transaction-oriented analytics

## IBM watsonx.data
Use for:
- governed data access
- analytical data foundation
- transaction/KYC/context integration

## IBM watsonx.ai
Use for:
- AI/ML workflows
- model development
- grounded investigator narrative generation

## IBM watsonx.governance
Use for:
- model governance
- monitoring
- explainability
- model metadata
- auditability

### Architecture

```text
Transaction / Event Layer
          ↓
   Governed Data Layer
          ↓
   Graph + Feature Layer
          ↓
       ML Models
          ↓
   Risk / Correlation Engine
          ↓
 Investigator Dashboard
          ↓
 Evidence Package
```

Only integrate IBM services that are actually available in the competition environment.

---

# 16. One-Month Preparation

## Week 1 — Foundation
- understand AML typologies
- learn graph basics
- design dataset
- create synthetic transaction generator
- finalize architecture

## Week 2 — ML
- build baseline
- XGBoost
- Isolation Forest
- feature engineering
- evaluation pipeline

## Week 3 — Graph + Product
- graph construction
- layering
- cycles
- dormant activation
- dashboard
- trace/timeline

## Week 4 — IBM + Demo
- IBM integration
- explainability
- evidence report
- performance testing
- final demo script

---

# 17. Scope — MUST HAVE

```text
✓ Synthetic banking dataset
✓ Transaction ingestion
✓ Temporal graph
✓ Layering detection
✓ Round-tripping detection
✓ Dormant-account detection
✓ Profile mismatch
✓ XGBoost
✓ Isolation Forest
✓ Path-level risk
✓ Explainability
✓ Investigator dashboard
✓ Fund tracing
✓ Evidence package
✓ At least one meaningful IBM integration
✓ Baseline comparison
✓ Measured metrics
```

## Nice-to-have

```text
• Real-time streaming
• SHAP
• GNN
• LLM investigator copilot
• Advanced governance UI
```

Do not sacrifice the working core for extra technologies.

---

# 18. Hero Demo

Use one synthetic case containing multiple signals:

```text
Dormant account
      ↓
₹18L received
      ↓
Rapid transfers
      ↓
Multiple intermediary accounts
      ↓
Circular relationship
      ↓
Profile mismatch
```

Then show:

```text
RISK = 94/100

Detected:
✓ Dormant activation
✓ Layering
✓ Circular flow
✓ High pass-through ratio
✓ Profile mismatch
```

Next:

**TRACE FUNDS**

→ animate the graph

Next:

**WHY FLAGGED?**

→ show evidence

Next:

**GENERATE CASE REPORT**

→ produce PDF/JSON

This should be the main live demo.

---

# 19. What Judges Must Understand in 60 Seconds

```text
1. Money laundering can look normal transaction-by-transaction.
2. The suspicious signal often appears in the fund journey.
3. FlowGuard turns the journey into a temporal graph.
4. ML + graph analytics detect and score suspicious paths.
5. Investigators can trace and understand the evidence.
6. IBM technologies provide the enterprise AI/data/governance foundation.
```

---

# 20. Final Pitch

> **“Traditional monitoring asks whether a transaction is suspicious. FlowGuard asks what story the money is telling.”**

### Full value proposition

> **FlowGuard AI is an explainable fund-flow intelligence system that combines temporal graph analytics, behavioural ML and customer context to detect complex fraud/AML patterns, trace the journey of funds, prioritize investigations and generate evidence-backed case packages.**

---

# 21. Important Boundaries

Do NOT claim:

- “No bank has this.”
- “Graph AML is our invention.”
- “The model guarantees fraud detection.”
- “We automatically file with FIU.”
- “This replaces a bank's AML platform.”

Instead:

> **FlowGuard is an intelligence and investigation layer designed to enrich existing monitoring with explainable, path-centric fund-flow analysis.**

---

# 22. Final Project Definition

## **FLOWGUARD AI**
### Dynamic, Explainable Fund-Flow Intelligence for Fraud Detection

### Core pipeline

```text
DATA
 ↓
ACCOUNT BEHAVIOUR
 ↓
TEMPORAL FUND-FLOW GRAPH
 ↓
GRAPH TYPOLOGIES
 ↓
ML + ANOMALY DETECTION
 ↓
CORRELATION / PATH RISK
 ↓
EXPLAINABLE ALERT
 ↓
INVESTIGATOR TRACE
 ↓
EVIDENCE PACKAGE
```

### Core technologies

**Python + Pandas + XGBoost + Isolation Forest + NetworkX + FastAPI + Streamlit/React + IBM watsonx / IBM Z components as available**

### Core proof

> **Show that combining transaction behaviour + graph structure + temporal patterns produces more useful, explainable and investigator-efficient fraud intelligence than a transaction-only baseline.**
