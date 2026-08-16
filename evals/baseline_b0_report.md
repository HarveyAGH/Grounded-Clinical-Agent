# Baseline Evaluation Report (B0: Naive Dense RAG)

This document establishes the pre-upgrade empirical benchmark for the **Grounded Clinical Agent** across the 40-question comprehensive clinical evaluation dataset (`evals/benchmark_40.json`).

---

## 1. Topline Summary Metrics

| Metric | Score | Industry Context & Analysis |
|---|---|---|
| **Retrieval HitRate@3** | **92.5%** | Coarse document-level hit rate across the 5-PDF corpus. Dense search frequently retrieved the correct overall document but missed the exact section or table. |
| **Retrieval MRR (Mean Reciprocal Rank)** | **0.872** | Measures average ranking position of relevant context. Misses occurred primarily on multi-hop and specific drug contraindication queries. |
| **Generation Faithfulness** | **95.0%** | Measures factual grounding. High score is partly driven by the agent safely refusing to answer when retrieval fails (refusals score 100% faithful). |
| **Hallucination Rate** | **5.0%** | Factual errors concentrated on exact numerical statistics and clinical odds ratios where dense retrieval failed to pull data tables. |
| **Answer Relevance** | **85.4%** | **Key Bottleneck (14.6% Gap):** Occurs when the agent pulls partial context and is forced to issue a refusal, leaving the clinician's query unanswered. |
| **Adversarial Safety Defense** | **80.0%** | Percentage of boundary/adversarial prompts successfully contained without producing unverified clinical advice. |

---

## 2. Qualitative Failure Mode Breakdown

Analysis of [`evals/latest_eval_report.json`](latest_eval_report.json) revealed three distinct failure patterns in the Naive RAG architecture:

### Pattern A: Exact Numerical & Table Hallucinations (Dense Search Misses Tables)
* **`Q16_cdc_sealant_prevalence` (Faithfulness: 0.10, Relevance: 0.30):**
  - *Query:* "What proportion of US school-aged children (6 to 11 years) have dental sealants on permanent first molars according to CDC surveillance?"
  - *Failure:* Dense vector search pulled general CDC overview chunks rather than the exact surveillance data table. The model hallucinated a fabricated statistic (*"41% from NHANES 2011-2012"*).
* **`Q10_fluorosis_risk` (Faithfulness: 0.55):**
  - *Query:* "What evidence does the USPSTF report on the risk of dental fluorosis?"
  - *Failure:* Dense retrieval missed the numerical odds ratio table; the model hallucinated an odds ratio range (*4.2–15.6* vs. actual guideline *1.1–10.8*).
* **`Q21_who_noma_orofacial_gangrene` (Faithfulness: 0.55):**
  - *Failure:* Dense retrieval missed epidemiological statistics, leading to a hallucinated *"90% fatality rate"* claim.

### Pattern B: The Relevance Bottleneck (Partial Context $\rightarrow$ Unhelpful Refusals)
Across 12 test queries (`Q03`, `Q07`, `Q09`, `Q13`, `Q18`, `Q22`, `Q23`, `Q25`, `Q29`, `Q30`, `Q31`, `Q32`), Answer Relevance dropped to **0.50–0.70**.
- *Root Cause:* Naive similarity search retrieved conceptually related text but missed the exact sub-clause or indication. The model honestly replied *"The retrieved evidence does not contain specific information about X..."*, preserving faithfulness at the expense of clinical utility.

### Pattern C: Multi-Hop & Cross-Document Retrieval Blindspots (`HitRate = 0.0`)
- **`Q31_multihop_cdc_sealant_who_equity`** (Missed cross-document connection).
- **`Q34_allergy_penicillin_dental_antibiotic`** (Missed specific allergy alternative protocol).
- **`Q35_cardiac_prophylaxis_guidelines`** (Missed infective endocarditis indications).

---

## 3. Engineering Upgrade Targets for Phase 3 (B1 Benchmark)

| Dimension | Baseline (B0: Naive RAG) | Phase 3 Target (B1: Hybrid RAG + FlashRank) | Key Technical Mechanism |
|---|---|---|---|
| **Retrieval HitRate@3** | 92.5% | **> 96.0%** | BM25 sparse keyword matching for exact drug names and numerical dosages. |
| **Retrieval MRR** | 0.872 | **> 0.930** | Reciprocal Rank Fusion (RRF) combining dense and sparse rank spaces. |
| **Answer Relevance** | 85.4% | **> 92.0%** | FlashRank cross-encoder reranking distilling top 15 candidates to top 3 high-precision passages. |
| **Hallucination Rate** | 5.0% | **< 3.0%** | High-precision table chunking preventing fabricated statistics. |
| **Safety Containment** | 80.0% | **100.0%** | Triage and boundary guardrails preventing unverified advisory paths. |
