# 🩺 Project 1: Grounded Clinical/Health Knowledge Agent

**Maps to:** Lucis, Clara, BillionToOne

**One-line pitch:** A RAG agent that answers questions from a real corpus of clinical/health guideline documents, refuses to answer without a citation, and reports a measured hallucination rate against an adversarial test set.

**What it demonstrates:** retrieval you can prove is trustworthy — the exact language these postings use ("retrieval a clinician would trust," "no hallucinations").

**Core components:**

- Ingestion + chunking pipeline over real public clinical guideline PDFs (not toy data)
- Vector store (Chroma or Qdrant) + reranking step
- Output schema requiring a citation field per claim — no citation, no answer
- A groundedness checker flagging any claim not traceable to a retrieved chunk
- Guardrail: input filter refusing out-of-scope requests (e.g. "diagnose me"), routed to an explicit "not medical advice" response

**Definition of done:** run 20 adversarial questions designed to bait a hallucination; report your catch rate as a number in the README.

<aside>
🛠️

**2026 tech stack:** LangGraph for orchestration · Chroma/Qdrant for vectors · Langfuse (open-source, OTel-native) for tracing instead of a hand-rolled dashboard.

</aside>