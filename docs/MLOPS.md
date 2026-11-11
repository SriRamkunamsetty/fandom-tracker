# FandomWatch MLOps & AI Engineering Guide

This document details the machine learning models, statistical mechanics, evaluation frameworks, and operational drift detection mechanisms implemented in FandomWatch.

---

## 1. Machine Learning Pipeline Architecture

```
[Social Media Comments] 
       │
       ▼
[Text Cleaning & Normalization]
       │
       ├─────────────────────────────────┬─────────────────────────────────┐
       ▼                                 ▼                                 ▼
[Sentence ABSA Engine]         [Dense Vector Embedder]        [Daily Aggregation Matrix]
(acting, story, price, ...)     (Semantic Anchor Hash)                     │
       │                                 │                                 ▼
       ▼                                 ▼                       [Sliding MAD Robust-Z]
[Aspect Sentiment Net Scores]    [Greedy Cosine Clustering]      (z >= 3.5, neg_share >= 0.35)
                                (Thematic Narrative Threads)               │
                                                                           ▼
                                                                 [Backlash Episode Merging]
                                                                           │
                                                                           ▼
                                                                 [Holt-Winters Forecaster]
                                                                 (7-14 Day Trend Projection)
                                                                           │
                                                                           ▼
                                                                 [Autonomous PR Crisis Agent]
                                                                 (Executive Brief & Mitigation)
```

---

## 2. Mathematical Formulations

### 2.1 Asymmetric Wilson Score Interval
Standard normal approximations ($\hat{p} \pm 1.96 \sqrt{\hat{p}(1-\hat{p})/n}$) collapse at extremes or small sample sizes. FandomWatch uses the Wilson score interval:

$$\hat{p} = \frac{k}{n}, \quad d = 1 + \frac{z^2}{n}, \quad c = \frac{\hat{p} + \frac{z^2}{2n}}{d}, \quad h = \frac{z}{d} \sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}$$
$$\text{CI}_{95\%} = [c - h, \, c + h]$$

### 2.2 Robust Anomaly Detection (MAD Scaling)
To avoid distortion from extreme viral spikes, FandomWatch utilizes Median Absolute Deviation:
$$\text{MAD} = \text{median}\left(|x_i - \text{median}(X)|\right)$$
$$z_i = 0.6745 \cdot \frac{x_i - \text{median}(X)}{\max(\text{MAD}, 0.05)}$$

### 2.3 Double Exponential Smoothing (Holt's Linear Trend)
Projects negative share evolution over future horizons:
- Level: $\ell_t = \alpha y_t + (1 - \alpha)(\ell_{t-1} + b_{t-1})$
- Trend: $b_t = \beta(\ell_t - \ell_{t-1}) + (1 - \beta)b_{t-1}$
- Forecast: $\hat{y}_{t+h} = \ell_t + h \cdot b_t$

---

## 3. Classifier Evaluation & Model Drift

### 3.1 Empirical Ground Truth Evaluation
Run the validation suite against your own human-labeled comments (`labels.csv`):

```bash
fandomwatch fandom-eval labels.csv --save
```

This calculates:
- Accuracy
- Macro-F1 score
- Per-class Precision, Recall, F1 for `pos`, `neu`, `neg`
- $3 \times 3$ Confusion Matrix
- Stores audit trail in `validation/fandom_eval.json` and records to `model_metrics` table.

### 3.2 LLM Benchmarking
Compare the internal engine against frontier models:

```bash
fandomwatch fandom-eval labels.csv --llm anthropic
fandomwatch fandom-eval labels.csv --llm gemini
```
