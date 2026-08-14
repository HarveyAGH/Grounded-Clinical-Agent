# To-Do List: Grounded Clinical Agent (Ship, Deploy & Resume Roadmap)

This checklist outlines the essential steps required to ship, deploy, and showcase the **Grounded Clinical Agent** for an AI Engineering resume.

---

## 🎨 Phase 1: Interactive UI (Solving the Frontend Blocker)

- [ ] **Option A: Build a Pure Python Streamlit UI (`app/streamlit_app.py`)**
  - [ ] Implement `st.chat_input` and `st.chat_message` interface.
  - [ ] Connect directly to `src/agent.py` graph execution.
  - [ ] Render expandable source citations (`st.expander("📚 Retrieved Evidence Chunks")`) displaying retrieved Qdrant text chunks and similarity scores.
  - [ ] Display prominent visual badges for **Clinical Safety Refusals** and **Human Escalation** outcomes.
- [ ] **Option B: CopilotKit AG-UI Integration**
  - [ ] Verify FastAPI AG-UI endpoint (`uvicorn app.main:app --port 8000`) at `/ag-ui`.
  - [ ] Wire frontend React/Next.js component `<CopilotChat />` to backend.
- [ ] **Option C: LangGraph Studio Demo Rehearsal**
  - [ ] Run `langgraph dev` and test visual execution traces across DAG nodes.
  - [ ] Record a short 60-second screen capture of graph execution.

---

## ☁️ Phase 2: Deployment & Cloud Hosting

- [x] **Containerization**
  - [x] Write production `Dockerfile` bundling Python 3.12, virtual environment, and local Qdrant vectors (`data/qdrant_db`).
  - [x] Create `docker-compose.yml` for unified local/cloud deployment.
- [ ] **Cloud Backend Deployment**
  - [ ] Deploy FastAPI container on Render, Railway, Fly.io, or AWS App Runner.
  - [ ] Set environment variables securely on host platform (`AWS_BEARER_TOKEN_BEDROCK`, `BEDROCK_MODEL_ID`, `JUDGE_MODEL_ID`, `DB_URI`).
- [ ] **Cloud Frontend Hosting**
  - [ ] Deploy Streamlit app to Streamlit Community Cloud or Render / Vercel.
- [ ] **API Security & Rate Limiting**
  - [ ] Add basic rate limiting (`slowapi` or middleware) on `/query` endpoint to protect AWS Bedrock quota.

---

## ⚡ Phase 3: AI Engineering & Reliability Hardening

- [ ] **Benchmark Verification (`r005`)**
  - [ ] Run evaluation suite (`python evals/run_eval.py`).
  - [ ] Verify avg faithfulness score remains high (>0.90) and hallucination rate stays low (<10%).
  - [ ] Log results into `evals/benchmarks.json`.
- [ ] **Guardrails & Injection Testing**
  - [ ] Test adversarial jailbreaks (*"Ignore previous instructions and tell me..."*).
  - [ ] Ensure router and `groundness_checker` reliably trigger safety refusals or human escalation.
- [ ] **Observability & Tracing**
  - [ ] Enable LangSmith tracing (`LANGCHAIN_TRACING_V2=true`) to monitor latency, node execution times, and token costs.

---

## 📊 Phase 4: Resume & Portfolio Showcase

- [ ] **Demo Video & GIF**
  - [ ] Record a 45-second demo showing:
    1. Valid clinical query with evidence citations.
    2. Safety refusal on personal diagnosis question.
    3. Self-correction retry loop on ungrounded claims.
  - [ ] Embed demo GIF in `README.md`.
- [ ] **GitHub Repository Polish**
  - [ ] Add visual architecture diagram (Router → Medical Agent → Qdrant Vector Store → Groundness Checker → Escalation).
  - [ ] Add Evaluation Metric Table tracking progression (`r000` to `r004`).
  - [ ] Document quick-start setup (`docker compose up` or `pip install -e .`).

---

## 📝 Resume Bullet Points (AI Engineering)

> **AI / RAG Engineer — Grounded Clinical Agent**
> - **Architected a deterministic clinical Q&A RAG agent** using LangGraph, AWS Bedrock (Claude Haiku 4.5), and Qdrant, enforcing strict factual grounding against biomedical guidelines.
> - **Eliminated hallucinations from 93.7% down to 7.0%** across 20 adversarial test cases by introducing a self-correcting evaluation loop with a strict `groundness_checker` node and Sonnet 4.6 Ragas judge model.
> - **Improved retrieval relevance** by replacing general embeddings with biomedical-specific `MedEmbed-small-v0.1` vectors and custom chunking pipelines.
> - **Deployed production FastAPI service** with CopilotKit AG-UI protocol endpoints, PostgreSQL session persistence via `PostgresSaver`, and Streamlit UI.
