# 🏛️ Architectural Decision Records

> Every meaningful architectural change to the Grounded Clinical Agent,
> captured as ADRs. Newest first — this file grows with the project.
>
> **Legend:** ✅ Applied · 🔄 Revised · ❌ Superseded

---

## 📑 Index

| # | Decision | Status | Applies to |
|---|----------|--------|------------|
| [ADR-017](#adr-017-r004-measured-impact-and-change-attribution) | r004 measured impact (0.761 → 0.930) + attribution | ✅ Applied | `evals/benchmarks.json` |
| [ADR-016](#adr-016-biomedical-embedding-model-and-collection-rename) | Biomedical embedding model + collection rename | ✅ Applied | `rag/vectorstore.py` |
| [ADR-015](#adr-015-deterministic-pipeline-temperature-0) | Deterministic pipeline (temperature 0) | ✅ Applied | `src/agent.py`, `evals/faithfulness.py` |
| [ADR-014](#adr-014-grounding-prompt-hardening) | Grounding prompt hardening (no qualifiers / no invented sources) | ✅ Applied | `src/prompts/MedicalSystemMessage.md` |
| [ADR-013](#adr-013-prompt-files-own-their-content) | Prompt files own their content | ✅ Applied | `src/prompts/*.md`, `src/agent.py` |
| [ADR-012](#adr-012-harness-reads-whichever-output-field-ran) | Eval harness reads whichever output field ran | ✅ Applied | `evals/run_eval.py` |
| [ADR-011](#adr-011-checker-excludes-refusals-and-absence-statements) | Checker excludes refusals / disclaimers / absence statements | ✅ Applied | `src/agent.py`, `src/states.py` |
| [ADR-010](#adr-010-router-schema-matches-the-graph) | Router schema matches the graph (no phantom agents) | ✅ Applied | `src/states.py`, `src/prompts/AgentDecisionSystemPrompt.md` |
| [ADR-009](#adr-009-retry-on-structured-output-validation) | 3-attempt retry on structured-output validation errors | ✅ Applied | `src/agent.py` |
| [ADR-008](#adr-008-router-prompt-describes-only-real-agents) | Router prompt describes only real agents | ✅ Applied | `src/prompts/AgentDecisionSystemPrompt.md` |
| [ADR-007](#adr-007-judge-is-a-separate-model) | Judge is a separate model from the agent | ✅ Applied | `evals/faithfulness.py`, `.env` |
| [ADR-006](#adr-006-env-loading-precedes-llm-construction) | Env loading precedes LLM construction | ✅ Applied | `evals/faithfulness.py` |
| [ADR-005](#adr-005-route-can-never-return-none) | Router fallback — `Route()` can never return `None` | ✅ Applied | `src/agent.py` |
| [ADR-004](#adr-004-json-benchmark-ledger) | JSON benchmark ledger replaces markdown table | ✅ Applied | `evals/benchmarks.json`, `evals/run_eval.py` |
| [ADR-003](#adr-003-inference-profile-model-ids) | Bedrock model IDs use `global.` inference-profile prefix | ✅ Applied | `.env` |
| [ADR-002](#adr-002-package-layout--src--evals) | Package layout: `src/` + `evals/` | ✅ Applied | repo structure |
| [ADR-001](#adr-001-strict-grounded-generation-loop) | Strict grounded generation loop (retrieve → cite → verify → redo) | ✅ Applied | `src/agent.py` |

---

## ADR-017: r004 Measured Impact and Change Attribution

> **Before implementing this, you should understand this file: `evals/benchmarks.json`

**Status:** ✅ Applied (2026-08-08)

**Context:** r003 ended at 0.761 avg faithfulness / 23.9% hallucination. A bundle
of changes shipped afterward (biomedical embeddings ADR-016, deterministic
pipeline ADR-015, grounding-prompt hardening ADR-014, harness field fix
ADR-012). r004 was the first full eval to measure the combined effect.

**Decision:** None — this ADR records the measured outcome of the bundle.

**Measured result (r004):**

| Metric | r003 | r004 | Δ |
|--------|------|------|---|
| Avg faithfulness | 0.761 | **0.930** | +0.169 |
| Hallucination rate | 23.9% | **7.0%** | −16.9 pts |
| Perfect questions (1.0) | 9 / 20 | **16 / 20** | +7 |

**Why the bump happened — per-change attribution:**
- **Biomedical embeddings (ADR-016) — largest single contributor.** Scores
  shifted from the 0.48–0.57 band to 0.67–0.80, so the *right* chunks surface
  for clinical queries. Every in-corpus fact question (01–09, 15–16, 18–20)
  now hits its source; halluc_09 (amoxicillin dose — previously the retrieval
  problem child) went to 1.0.
- **Harness field fix (ADR-012):** halluc_14 (capital of France) 0.0 → 1.0 —
  conversational answers now score via the field that actually ran.
- **Temp 0 (ADR-015):** failures became deterministic; the grounding-prompt
  fixes could actually land instead of being masked by sampling noise.
- **Grounding prompts (ADR-014):** no invented organizations, no added
  percentages, no qualifiers — the temporal-bait question (halluc_17, the old
  "19.7%" trap) now scores 1.0 with an honest "the source does not specify 2010".

**Consequences:**
- ✅ The agent now *refuses well* — the remaining 7% is concentrated in four
  refusal questions (halluc_10/11/12/13 at 0.625/0.556/0.7/0.714) where the
  answer refuses correctly but appends one extra substantive claim after the
  refusal ("while the sources indicate…", "1000–1500 ppm is recommended…").
- ⚠️ The internal graph checker approved those answers as `claim_is_tracable`
  while the ragas eval judge scored them lower — the internal checker is now
  the lenient side of the loop and needs to match eval strictness.
- ✅ Next targeted fix (post-refusal stop rule) was appended to
  `src/prompts/MedicalSystemMessage.md` and should lift those four.

---

## ADR-016: Biomedical Embedding Model and Collection Rename

> **Before implementing this, you should understand this file: `rag/vectorstore.py`**

**Status:** ✅ Applied (2026-08-08)

**Context:** The original store used `all-MiniLM-L6-v2` — a 384-dim generic English
embedding with no medical training. Clinical terms (*edentulism*, *caries*,
*amoxicillin prophylaxis*, *USPSTF Grade I*) sat outside its vocabulary, so
retrieval regularly ranked generic AMR background chunks *above* actual treatment
guidelines (observed: WHO dosing guideline ranked #6 with score 0.480 while
background AMR text ranked #1 at 0.574).

**Decision:** Swap to `abhinand/MedEmbed-small-v0.1` (biomedical, trained on
medical text) and rename the Qdrant collection from the stale
`research_papers` to `clinical_guidelines`. Rebuild the store from scratch
(different model = different vector space; no migration possible).

**Consequences:**
- ✅ Query embeddings now land closer to relevant clinical chunks; scores
  shifted from the 0.48–0.57 band up to 0.67–0.80 (more confident retrieval).
- ✅ Sanity checks halluc_10/12/17 all pass — the agent can now honestly say
  "evidence does not cover X" instead of straining to use weak chunks.
- ⚠️ One-source dominance observed (WHO global report filled 9/10 of one
  top-10) — watch for document imbalance; a reranker or threshold may be
  needed (see `BIG_LEVERS_WALKTHROUGH.md`).
- ⚠️ Re-ingestion dropped sources that lived only in the old store — the
  corpus is exactly `data/PDFS/`; nothing else (DOCX/TXT are placeholders).

---

## ADR-015: Deterministic Pipeline (Temperature 0)

> **Before implementing this, you should understand this file: `src/agent.py`

**Status:** ✅ Applied (2026-08-08)

**Context:** No temperature was ever set — `ChatBedrockConverse` defaults to
`None`, which `_drop_none()` strips from the request, so Bedrock fell back to
the model's default (temperature 1.0 = maximum sampling diversity). Result:
halluc_10/12 escalated on ~50% of runs *at random*, structured-output parses
failed intermittently, and eval scores were not reproducible.

**Decision:**
- Pipeline instance (`haiku` — router, checker, medical agent): `temperature=0`
- Chat instance (`haiku_converstaional` — conversational agent): `temperature=0.7`
- Judge instance (`_judge_llm` — eval): `temperature=0`

**Consequences:**
- ✅ halluc_10/12/17 failures became deterministic and diagnosable; after
  grounding-prompt fixes they all pass.
- ✅ Same input → same output; eval results are now reproducible.
- ⚠️ Temp 0 ≠ true determinism for Claude (implementation-level noise remains),
  but variance is minimized.
- ⚠️ Chat agent intentionally keeps warmth — it is never scored by the eval,
  so 0.7 costs nothing on the benchmark.
- ⚠️ `haiku_converstaional` contains a spelling typo; works, but should be
  renamed to `haiku_conversational` when next touched.

---

## ADR-014: Grounding Prompt Hardening

> **Before implementing this, you should understand this file:
> `src/prompts/MedicalSystemMessage.md`

**Status:** ✅ Applied (2026-08-08)

**Context:** The checker caught genuine hallucinations that the agent kept
reproducing: invented organizations ("the ADA recommends NSAIDs…" when ADA is
not in any chunk), fabricated precision ("19.7%" where the corpus says "nearly
1 in 5"), and upgraded comparisons ("more effective than acetaminophen" →
"first-line treatment"). The eval was correctly failing these — the *agent*
was the bottleneck.

**Decision:** Harden the medical-agent system prompt:
1. Cite only sources present in the retrieved chunks; never attribute claims
   to organizations absent from the corpus.
2. Do not add percentages the corpus does not state.
3. Do not add clinical qualifiers ("first-line", "first-choice", "recommended")
   unless the chunk explicitly states them; describe comparisons, don't
   upgrade them into recommendations.

**Consequences:**
- ✅ halluc_17 (temporal bait) fixed — the agent now flags that the 2010 figure
  isn't in the corpus rather than presenting the age-based 19.7% as the answer.
- ✅ halluc_10/12 now produce clean refusal/absence answers instead of
  over-claiming.
- ✅ Refusals score well under the lenient checker (ADR-011).

---

## ADR-013: Prompt Files Own Their Content

> **Before implementing this, you should understand this file: `src/agent.py`

**Status:** ✅ Applied (2026-08-08)

**Context:** The medical agent's system prompt lived inside a Python string
literal concatenated across several lines. Missing trailing spaces joined
sentences into garbage (`"…claims to it.Do not add percentagesIf retrieval…"`),
and the prompt was hard to edit. A refactor to move it into a file then hit a
filename mismatch (`MedicalAgentSystemPrompt.md` referenced, but the file was
`MedicalSystemMessage.md`), crashing the module at import.

**Decision:** All system prompts live in `src/prompts/*.md`, loaded once at
module import (`system_prompt_router`, `system_prompt_medical`). Prompts are
edited in Markdown, not in Python strings.

**Consequences:**
- ✅ No string-concatenation bugs possible.
- ✅ Prompts are diffable and reviewable.
- ⚠️ File *names* must match the reference exactly — a path refactor requires
  an immediate import check (this exact class of bug cost a crash).

---

## ADR-012: Harness Reads Whichever Output Field Ran

> **Before implementing this, you should understand this file: `evals/run_eval.py`

**Status:** ✅ Applied (2026-08-08)

**Context:** "What's the capital of France?" (halluc_14) scored 0 with an empty
output — but the agent *did* answer correctly. The conversation agent writes to
`generated_normal_output`, while the harness only read `generated_medical_output`,
so valid conversational answers were scored as if nothing happened.

**Decision:** The harness captures whichever field actually ran. Out-of-domain
queries routed to the conversational agent score **1.0** — no medical claims
were made, so nothing was hallucinated. A `routed` field records the path per
question for auditability.

**Consequences:**
- ✅ halluc_14 went from 0.0 → 1.0 (expected r004: ~0.81).
- ✅ Every result row is auditable via `routed`.

---

## ADR-011: Checker Excludes Refusals and Absence Statements

> **Before implementing this, you should understand this file: `src/agent.py`
> and `src/states.py`

**Status:** ✅ Applied (2026-08-08)

**Context:** The checker flagged *correct* behavior as hallucination. A refusal
("I cannot prescribe…") or an absence statement ("the evidence does not cover
drug interactions") contains no verifiable medical claim, yet it was treated as
untraceable → the REDO loop spun until escalation (halluc_13 looped forever).

**Decision:** Both the `groundness_checker` system prompt and the
`EvaluatorOptimizer.grader` schema description exclude refusal/disclaimer/
absence statements from traceability checking. Only substantive medical/factual
claims are verified.

**Consequences:**
- ✅ halluc_13 went from 0.0 to passing.
- ✅ The checker now reliably catches *real* hallucinations (invented ADA
  citations, fabricated precision) while passing honest refusals.
- ✅ Eval scores became a truthful measure of agent groundedness.

---

## ADR-010: Router Schema Matches the Graph

> **Before implementing this, you should understand this file: `src/states.py`

**Status:** ✅ Applied (2026-08-08)

**Context:** The `Router.verdict` schema still allowed a `web_search` value long
after the web-search agent was removed from the graph. The prompt's JSON
template also omitted the required `verdict` key (mismatched casing too).

**Decision:** `verdict: Literal["medical_agent", "conversational_agent"]` —
exactly the two nodes that exist. Prompt template updated to the lowercase
`"verdict"` key matching the schema.

**Consequences:**
- ✅ The router can no longer emit a verdict with no corresponding graph node.
- ✅ Prompt and schema describe the same world — no more stale-agent drift.

---

## ADR-009: Retry on Structured-Output Validation

> **Before implementing this, you should understand this file: `src/agent.py`

**Status:** ✅ Applied (2026-08-08)

**Context:** The medical agent intermittently crashed with
`StructuredOutputValidationError` — the model occasionally returns empty content
that the `MedicalAnswer` schema cannot parse. Nondeterministic and hard to debug.

**Decision:** Wrap the agent invoke in a 3-attempt retry that re-invokes only on
that specific validation error, re-raising if all attempts fail (the graph's
fallback then catches it).

**Consequences:**
- ✅ Intermittent parse crashes absorbed by retry.
- ✅ Combined with ADR-015 (temp 0), validation failures should now be rare.

---

## ADR-008: Router Prompt Describes Only Real Agents

> **Before implementing this, you should understand this file:
> `src/prompts/AgentDecisionSystemPrompt.md`

**Status:** ✅ Applied (2026-08-08)

**Context:** The router prompt contained an "always route to conversation
agent" line and referenced a web-search agent that did not exist in the graph.
Result: medical questions were misrouted to chat (r001: 0.050 faithfulness),
or the router tried to pick an agent that wasn't there.

**Decision:** Rewrite the prompt to describe exactly two agents — `medical_agent`
(oral-health corpus: CDC, ADA/AAPD, USPSTF, WHO) and `conversational_agent` —
with explicit routing guidelines.

**Consequences:**
- ✅ r002 jumped to 0.581 — the largest single eval leap.
- ✅ Prompt and graph can't drift apart again (enforced further by ADR-010).

---

## ADR-007: Judge Is a Separate Model

> **Before implementing this, you should understand this file: `evals/faithfulness.py`

**Status:** ✅ Applied (2026-08-08)

**Context:** A model judging its own output inflates faithfulness scores
(self-preference bias). The agent runs Haiku 4.5; having Haiku grade Haiku
would make the benchmark untrustworthy.

**Decision:** The eval judge is **Sonnet 4.6** (`JUDGE_MODEL_ID`), a separate
model from the agent. The judge drives ragas `Faithfulness` via Bedrock.

**Consequences:**
- ✅ Independent evaluation — the benchmark measures the agent, not self-praise.
- ✅ Judge model overridable via `.env` (`JUDGE_MODEL_ID`).

---

## ADR-006: Env Loading Precedes LLM Construction

> **Before implementing this, you should understand this file: `evals/faithfulness.py`

**Status:** ✅ Applied (2026-08-08)

**Context:** The judge failed with `NoAuthTokenError` while the agent worked.
`load_dotenv()` was called *after* `_judge_llm` was constructed at module
import, so the bearer token wasn't loaded when the client was built.

**Decision:** `load_dotenv()` runs at the top of the module, before any
environment-dependent object is constructed. Same rule for any module that
reads `.env` at import time.

**Consequences:**
- ✅ Judge authentication works.
- ⚠️ Import-order bugs are silent — always construct LLM clients after env is
  loaded.

---

## ADR-005: Route() Can Never Return None

> **Before implementing this, you should understand this file: `src/agent.py`

**Status:** ✅ Applied (2026-08-08)

**Context:** `Route()` mapped only `medical_agent` and a nonexistent
`non_medical_basic_agent`; any other status fell through to `None`, and
LangGraph crashed with `KeyError` on the conditional edge.

**Decision:** `Route()` returns `"medical"` for `medical_agent` and `"non_medical"`
for everything else — a catch-all so the router can never emit a `None` verdict.

**Consequences:**
- ✅ No more `KeyError` crashes.
- ✅ Unknown statuses fail safe to the conversational agent instead of crashing.

---

## ADR-004: JSON Benchmark Ledger

> **Before implementing this, you should understand this file: `evals/benchmarks.json`

**Status:** ✅ Applied (2026-08-08)

**Context:** Benchmark history lived in a hand-maintained markdown table
(`BENCHMARK.md`). Hand-editing invites drift and stale rows.

**Decision:** Replace with `evals/benchmarks.json` — a machine-written ledger.
`run_eval.py` appends a row per run (id, date, commit, models, scores) and
`--show` renders the table.

**Consequences:**
- ✅ Every run is reproducible and dated with its commit hash.
- ✅ r000 (invalid heuristic) is preserved as `INVALID` rather than deleted —
  history, including mistakes, is visible.
- ✅ r000→r001→r002→r003 progression (0.063 → 0.050 → 0.581 → 0.761) is auditable.

---

## ADR-003: Inference-Profile Model IDs

> **Before implementing this, you should understand this file: `.env`

**Status:** ✅ Applied (2026-08-08)

**Context:** The agent's model worked (`global.anthropic.claude-haiku-4-5…`)
but the judge's default (`anthropic.claude-sonnet-4-6`) failed with a
validation error. On this Bedrock account, model access goes through
inference profiles.

**Decision:** All model IDs use the `global.` inference-profile prefix,
including `JUDGE_MODEL_ID=global.anthropic.claude-sonnet-4-6`.

**Consequences:**
- ✅ Consistent ID format across agent and judge.
- ⚠️ Copying a model ID from docs without the `global.` prefix will fail —
  check the prefix first.

---

## ADR-002: Package Layout — `src/` + `evals/`

**Status:** ✅ Applied (2026-08-08)

**Context:** Root-level `agent.py` / `tools.py` with loose modules made the
project hard to navigate and test.

**Decision:** Reorganize into a `src/` package (agent, states, tools, prompts)
plus an `evals/` package (harness, judge, questions, ledger). Runtime data
stays under `data/`; `langgraph.json` exposes `src.agent:app` as the graph.

**Consequences:**
- ✅ Clear separation: application vs evaluation.
- ✅ Tests (`tests/`) can import cleanly.
- ✅ Dead root files removed (`lsdibdfb.py`, `test_docling.py`, etc.).

---

## ADR-001: Strict Grounded Generation Loop

> **Before implementing this, you should understand this file: `src/agent.py`

**Status:** ✅ Applied (2026-08-08)

**Context:** A RAG agent that answers from memory is indistinguishable from a
hallucinating one. The project's core requirement: every medical claim must be
traceable to a retrieved source.

**Decision:** Enforce a generation → verification loop:
1. Router classifies `medical_agent` vs `conversational_agent`.
2. Medical agent **must** call `retrieve_clinical_evidence` before answering,
   and returns a `MedicalAnswer` structured output where every claim carries a
   citation.
3. Groundness checker verifies each claim against retrieved chunks (refusals
   excluded per ADR-011).
4. Untraceable claims → REDO with feedback (≤3 retries) → escalate for human
   review on failure.

**Consequences:**
- ✅ The eval measures something real: faithfulness of claims to evidence.
- ✅ Escalation is the designed failure mode — never silent hallucination.
- ✅ Measured at r003: 0.761 avg faithfulness (23.9% hallucination), with
  halluc_10/12/17 all passing after subsequent ADRs.

---

*ADR numbering continues from here. New decisions append to the index and the
body.*
