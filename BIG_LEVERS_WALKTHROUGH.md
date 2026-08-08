# Big Lever Walkthrough: The Ingestion Pipeline

The agent is only as grounded as its retrieval, and retrieval is only as good as
the ingestion pipeline that built the store. This walkthrough covers the two
levers that will move the eval needle most after the prompt/checker fixes:

1. **Embedding model upgrade** — `all-MiniLM-L6-v2` → a biomedical model
2. **Similarity threshold in retrieval** — stop feeding the agent garbage chunks

---

## The pipeline, end to end

```
data/PDFS/*.pdf
    │  rag/doc_parser.py        (docling → markdown)
    ▼
data/raw/*.md
    │  rag/content_processor.py (header split → size split, 1000/200)
    ▼
chunks (Document, metadata["source"] = filename)
    │  rag/vectorstore.py       (HuggingFaceEmbeddings → Qdrant)
    ▼
data/qdrant_db/  (collection "research_papers")
    │  rag/retrieval.py         (similarity_search_with_score, k=3)
    ▼
src/tools.py     (formats chunks as [Source i: file, relevance: 0.xxx])
    │
    ▼
agent / checker / judge
```

Entry point: `python -m rag.ingest` — run ONCE per corpus update, never on
startup (it re-embeds everything).

---

## Lever 1: Embedding model upgrade

> **Before implementing this, you should understand this file: `rag/vectorstore.py`**

### What's there today

```python
embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
```

`all-MiniLM-L6-v2` is the default Swiss-army embedding: 384-dim, ~23M params,
fast, runs fine on CPU. But it's generic English — it has never seen medical
training data. Dental/clinical terms like *edentulism*, *amoxicillin
prophylaxis*, *caries*, or *USPSTF Grade I* are outside its vocabulary.

### Why this is the highest-leverage change

Every score the agent and the checker see flows through this model. A query
embedding that lands far from the right chunks means the agent gets the *wrong*
evidence and either answers from weak chunks (low faithfulness) or hallucinates
to compensate. You can fix prompts all day; retrieval quality caps what any
prompt can do.

### Candidate models

| Model | Dims | Size | Notes |
|---|---|---|---|
| `all-MiniLM-L6-v2` (current) | 384 | ~90MB | generic, fast, CPU-friendly |
| `BAAI/bge-small-en-v1.5` | 384 | ~130MB | better general retrieval, same dims, drop-in |
| `pritamdeka/S-PubMedBert-MS-MARCO` | 768 | ~420MB | **biomedical**, trained on PubMed + MS MARCO — the best fit for clinical text |
| `BAAI/bge-large-en-v1.5` | 1024 | ~1.3GB | strongest general, heavy for CPU ingest |

Recommendation: start with **`pritamdeka/S-PubMedBert-MS-MARCO`** — it's the
only one in the list actually trained on medical text, which is exactly your
domain. If CPU ingest time hurts, drop to `bge-small-en-v1.5`.

### How to do it

1. Change `model_name` in `rag/vectorstore.py` (one line).
2. **Delete `data/qdrant_db/`** — you MUST rebuild. Different model = different
   vector space = the old collection is meaningless. There is no migration.
3. Re-run `python -m rag.ingest`.
4. Sanity-check retrieval on a few queries before evaluating.

### Gotchas

- **Dimension mismatch**: Qdrant stores vectors with a fixed dimension per
  collection. 384 → 768 changes the dims, so even "just append" is impossible —
  rebuild, full stop.
- **Ingest cost**: the PubMed model is ~4× heavier. Ingest is one-time, so it's
  fine; per-query embedding is also slower but negligible vs. the LLM call.
- **The collection is named `"research_papers"`** — a leftover from the original
  project. Rename it while you're rebuilding (e.g. `clinical_guidelines`).
  It's the same one-line change.
- **Consistency**: `build_vectorstore` and `load_vectorstore` must use the SAME
  model. They already share the module-level `embedding_model` — keep it that
  way. If you ever see dimension errors at load time, the model drifted from
  ingestion.

---

## Lever 2: Similarity threshold in retrieval

> **Before implementing this, you should understand this file: `rag/retrieval.py`
> AND `src/tools.py`**

### What's there today

```python
def retrieve_chunks_with_scores(query: str, k: int = 3):
    return _get_store().similarity_search_with_score(query=query, k=k)
```

And in `src/tools.py`, `retrieve_clinical_evidence(query, k=5)` takes whatever
comes back — **no relevance floor**. If Qdrant returns 5 chunks with similarity
0.31, 0.28, 0.26, 0.24, 0.21, the agent gets all 5 as "evidence" and will
strain to use them.

### Why this matters

halluc_12 ("bump on the roof of my mouth") is the canonical case: the corpus
genuinely has **no** benign-bump content. Retrieval still returns its closest
chunks (oral cancer epidemiology) because top-k always returns *something*.
The agent then has to talk about oral cancer and hedge — which is why the
checker kept flagging invented guidance like "any lesion should be evaluated by
a dentist". A similarity floor would let retrieval honestly say **"no relevant
results"** and the agent could answer "this isn't covered" cleanly.

### What the score numbers actually mean

Qdrant (via `langchain-qdrant`) reports **similarity**, higher = better:
- ~0.6–0.7+ → clearly relevant (same topic, matching terms)
- ~0.4–0.6 → fuzzy, partial overlap
- < 0.4 → junk — closer to the query embedding than the average random chunk,
  but not evidence

**Do NOT hardcode 0.5 blind.** First add a debug print and look at the real
score distribution for a few in-corpus queries (halluc_01–05, which all pass)
vs. out-of-corpus ones (halluc_12). Pick the threshold where the good queries
clear it and the bad ones fall below. That's 15 minutes of measurement that
saves you from a magic number.

### How to do it

1. Add a `MIN_SIMILARITY` constant (start ~0.45, tune from real scores).
2. In `retrieve_chunks_with_scores`, filter `results` to scores ≥ threshold.
3. Keep `src/tools.py`'s "No relevant clinical guidelines found" branch — it
   already exists and now it will actually fire sometimes.
4. Re-run the sanity checks: halluc_12 should now produce a clean refusal
   instead of a marginal answer.

### Gotchas

- **Don't filter in `tools.py` alone** — the threshold is a retrieval policy,
   keep it in `retrieval.py` so every caller benefits.
- **k mismatch**: the tool calls `retrieve_clinical_evidence(query, k=5)` but
   `retrieval.py` defaults to `k=3`. Align them while you're in there (the
   threshold matters more than k, but inconsistent defaults are how bugs hide).
- **Truncation in `tools.py`**: chunks > 2000 chars get cut mid-sentence
   (`"... [truncated]"`). If a claim's evidence sits past the cut, the checker
   can't trace it. Consider bumping the cap or splitting before ingest instead
   (the 1000-char chunk size in `content_processor.py` already keeps most
   chunks under the cap).

---

## What this unlocks

With the biomedical embedding + a real similarity floor:

- **halluc_12 type** (no corpus coverage): clean "not covered" answers instead
  of strained half-answers → the checker stops flagging invented guidance.
- **halluc_10 type** (drug interaction): the right WHO/CDC chunks surface with
  higher confidence, so the agent's "no interaction data in evidence" refusal
  is grounded in actually-strong retrieval.
- **Everything else**: better top-k means the checker and judge see more
  relevant context, which raises faithfulness across the board — the r004 →
  r005 jump should be bigger than r003 → r004 was.

## Suggested order

1. Measure current score distribution (5 min).
2. Add threshold → sanity-check halluc_12 (Lever 2 is cheap, do it first).
3. Swap embedding model + rebuild + rename collection → sanity-check retrieval
   (Lever 1, then re-run full eval for r005).
