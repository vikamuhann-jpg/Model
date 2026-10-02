# ADR 017: Logistic Regression and Isolation Forest Dropped

**Date:** 2026-09-30
**Status:** Accepted

## Context
The original directive order listed Logistic Regression and Isolation Forest as models to be evaluated. They were omitted from the final shipped system, and this record documents why.

## Decision

### Logistic Regression
Logistic Regression was evaluated as a linear baseline but was dropped without further tuning. The dataset relies heavily on non-linear interactions between account behaviors and graph structural features (like fan-in and fan-out patterns). A linear model is intrinsically unable to capture these conditional relationships without massive manual feature engineering, and consistently performed poorly on PR-AUC compared to tree-based models like XGBoost and neural networks.

### Isolation Forest
Isolation Forest was evaluated as an unsupervised anomaly detection arm. While the dataset is highly imbalanced, the laundering typologies are structural and leave specific graph signatures that provide strong supervised signals. The unsupervised Isolation Forest was an early experiment that did not improve PR-AUC over the supervised XGBoost model alone. It was dropped to reduce pipeline complexity and latency at inference time.

## Consequences
- The final FlowGuard system relies entirely on supervised models which better handle the complex non-linear feature space.
- The pipeline is simplified by not requiring an unsupervised scoring arm or linear baseline.
