---
title: Grounded Clinical Agent
emoji: 🩺
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 5.20.0
app_file: app.py
pinned: false
---

# Grounded Clinical Agent

A LangGraph-powered clinical Q&A agent that answers dental-health questions **only from an ingested corpus of clinical guidelines** — and refuses to make claims it cannot trace back to a retrieved source.

Every answer passes through a verification loop: the agent retrieves evidence, generates a citation-enforced answer, a groundness checker verifies each claim against the retrieved chunks, and anything unverifiable gets re-generated or escalated for human review.

## How it works

```
user query
    │
    ▼
┌──────────────┐   medical_agent / conversational_agent
│ query_validator│──────────────────────────────┐
│   (router)    │                               │
└──────┬───────┘                               │
       │                                        │
       ├── medical ──► medical_agent ──► checker ──► success (END)
       │                      ▲                  │  │
       │                      │  REDO_NEEDED     │  ├─ MAX_LOOP_REACHED ─► escalate
       │                      └──────────────────┘  │
       └── non-medical ──► conversational_agent ────► END
```

1. **Router** (`src/agent.py` → `Router_function`) classifies the query as `medical_agent` or `conversational_agent`.
2. **Medical agent** (Haiku 4.5 via Bedrock) must call `retrieve_clinical_evidence` at least once, then returns a `MedicalAnswer` structured output — every claim carries a citation to a source chunk.
3. **Groundness checker** (Sonnet 4.6) reviews the answer claim-by-claim against the retrieved chunks. Refusal/disclaimer/absence statements are excluded; only substantive medical claims are verified.
4. If any claim is untraceable, the agent revises with feedback (up to 3 retries), then escalates for human review.

## Repository layout

```
├── src/
│   ├── agent.py            # LangGraph workflow (router, medical agent, checker, fallbacks)
│   ├── states.py           # Graph state + structured-output schemas (Router, MedicalAnswer, EvaluatorOptimizer)
│   ├── tools.py            # retrieve_clinical_evidence tool (Qdrant-backed)
│   └── prompts/
│       └── AgentDecisionSystemPrompt.md   # Router system prompt
├── rag/
│   ├── ingest.py           # PDF → markdown → chunks → vector store (run once per corpus update)
│   ├── doc_parser.py       # PDF parsing (docling)
│   ├── content_processor.py# chunking
│   ├── vectorstore.py      # Qdrant persistence (local, MedEmbed-small biomedical embeddings)
│   └── retrieval.py        # similarity search with scores
├── evals/
│   ├── run_eval.py         # 20-question faithfulness eval, auto-records runs in benchmarks.json
│   ├── faithfulness.py     # ragas Faithfulness judge (Sonnet 4.6, separate from the agent)
│   ├── adversarial_questions.json  # the 20 eval questions
│   ├── eval_results.json   # latest per-question results
│   └── benchmarks.json     # ledger of all runs (r000, r001, ...)
├── data/                   # PDFS/ (raw clinical PDFs), raw/ (parsed markdown), qdrant_db/ (vector store)
├── error_book.md           # log of errors hit and how they were fixed
└── HOW_TO_GUIDE.md         # deep-dive implementation notes
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Create `.env` (see `.env.example`-style keys in `langgraph.json` → `env`):

```
AWS_BEARER_TOKEN_BEDROCK=...
BEDROCK_REGION=us-east-1
BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0      # agent model
JUDGE_MODEL_ID=global.anthropic.claude-sonnet-4-6                      # eval judge model
```

> Both model IDs use the `global.` inference-profile prefix — the judge must be a **different** model from the agent to avoid self-preference bias in evals.

## Ingesting the corpus

Place clinical PDFs in `data/PDFS/`, then:

```bash
python -m rag.ingest
```

This parses → chunks → embeds into a local Qdrant store at `data/qdrant_db/`. Re-run only when the corpus changes.

## Running the agent

### Interactive CLI Mode
```bash
python src/agent.py
```

### Python API Usage
```python
from src.agent import app
state = app.invoke({"user_query": "Is it safe to take ibuprofen with amoxicillin for a dental infection?"})
print(state["generated_medical_output"])
```

## Docker Deployment

The application is containerized with a multi-stage `Dockerfile` and `docker-compose.yml` bundling the Python runtime, dependencies, and local Qdrant vectors (`data/qdrant_db/`).

### Option A: Using Docker Compose (Recommended)

1. **Build and start container in the background**:
   ```bash
   docker compose up --build -d
   ```
2. **View live logs**:
   ```bash
   docker compose logs -f
   ```
3. **Stop container**:
   ```bash
   docker compose down
   ```

### Option B: Using Docker CLI Directly

1. **Build the image**:
   ```bash
   docker build -t grounded-clinical-agent:latest .
   ```
2. **Run container with `.env` file**:
   ```bash
   docker run -d --name clinical-agent -p 8000:8000 --env-file .env grounded-clinical-agent:latest
   ```

### Verifying the Container

- **OpenAPI Docs**:
  ```bash
  curl -I http://localhost:8000/docs
  ```
- **REST Clinical Query (`/query`)**:
  ```bash
  curl -X POST http://localhost:8000/query \
    -H "Content-Type: application/json" \
    -d '{"query": "What is the recommended antibiotic prophylaxis for infective endocarditis?"}'
  ```
- **CopilotKit AG-UI Endpoint**:
  Available at `http://localhost:8000/ag-ui`.

## Evaluating

```bash
python evals/run_eval.py        # runs all 20 adversarial questions, appends a row to benchmarks.json
python evals/run_eval.py --show # print the run ledger
```

The eval measures **faithfulness**: the fraction of claims in the answer actually supported by the retrieved chunks. Questions span in-corpus facts, fabricated-statistic bait, drug dosage/interaction, personal diagnosis, refusal requests, out-of-domain queries, temporal bait, and cross-document consistency.

### Run history

| Run | Avg faithfulness | Hallucination | Notes |
|-----|-----------------|---------------|-------|
| r000 | 0.063 | 93.7% | INVALID — ragas import broken, heuristic fallback measured token overlap, not faithfulness |
| r001 | 0.050 | 95.0% | Router broken — most queries routed to the wrong agent |
| r002 | 0.581 | 41.9% | First real baseline after router + judge fixes |
| r003 | 0.761 | 23.9% | Checker prompt fixed — refusals no longer punished as hallucinations |

## Known limitations / next fixes

- The medical agent occasionally **cites sources not in the corpus** (e.g. "the ADA recommends…" when only CDC/WHO chunks were retrieved) and **fabricates precision** (e.g. "19.7%" where the corpus says "nearly 1 in 5"). The checker catches these correctly — the agent prompt needs stronger grounding instructions.
- No reranking or hybrid (sparse) retrieval yet — plain similarity search only (`rag/retrieval.py`).
- Out-of-domain queries are scored 1.0 by the harness since no medical claims are made (auditable via the `routed` field in `eval_results.json`).

## Tests

```bash
pytest
```
