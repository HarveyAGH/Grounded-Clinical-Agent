# UI Components Reference — Grounded Clinical Agent

Companion doc to the Next.js chat UI in `ui/`. Explains the architecture
contract, the files you own, how to extend the UI for new graph features,
and the exact recipes for common changes (new tool, memory, new output
field, latency improvements).

> Status: reflects the current working tree. The Python graph in `src/` is
> **not** touched by any of this — the UI is a pure client of the graph's
> state values.

---

## 1. Architecture: the 2-field contract

The UI and the Python graph communicate through a **thin state contract**.
Nothing else leaks across the boundary.

```
INPUT  (per user turn, top-level graph state input):
  { "user_query": "<the user's last message text>" }

OUTPUT (graph state values, read by the UI):
  final_answer                 -> preferred answer text (synthesizer)
  generated_medical_output     -> fallback answer (medical path / escalation)
  generated_normal_output      -> fallback answer (conversational path)
  retrieved_chunks             -> string[] of "[Source N: <file>, relevance: <score>]\n<chunk>"
  status                       -> "escalated" on fallback/eval_fallback nodes
  generated_output_valid_or_not -> "claim_is_tracable" | "claim_not_tracable"
```

Rules the UI enforces:

- **Never send the `messages` array** to the graph. The graph's `messages`
  channel holds tool-call JSON that the UI must not render or echo.
- **Never render the `messages` channel.** The clean answer lives in the
  state values above, not in `messages`.
- **Fresh thread per user turn.** The graph is single-turn by design: its
  checkpointer accumulates `messages`/`Feedback` across runs, and the medical
  agent's `elif state.get("Feedback")` branch would re-answer the previous
  turn. Each turn therefore runs on a new thread (see `assistant.tsx`).

---

## 2. Files you own (4)

| File | Role | You edit when… |
|---|---|---|
| `ui/app/assistant.tsx` | Runtime wiring: custom `stream` / `create` / `load`, `GroundedMetadata` type | Output contract changes; thread lifecycle changes (e.g. memory) |
| `ui/components/assistant-ui/grounded-message.tsx` | Renders one assistant message: refusal banner + collapsible Sources | Citation UI, refusal detection, answerText display |
| `ui/components/assistant-ui/composer-header.tsx` | Agent identity header above the composer + rotating streaming status | Agent name, status copy, loading animation phases |
| `ui/lib/chatApi.ts` | `ASSISTANT_ID` (`"agent"`), `createClient()` | Renaming the graph, changing API URL handling |

Config: `ui/.env.local` (API URL + assistant id). Proxy: `ui/app/api/[..._path]/route.ts`
(keep — forwards `/api/*` to `LANGGRAPH_API_URL`).

The remaining files under `ui/` are the assistant-ui scaffold (shadcn
components, thread primitives, markdown renderer) — treat as library code.
Template leftovers to ignore: `ui/backend/agent.ts`, `ui/langgraph.json`,
`help.md`.

---

## 3. Running it

```bash
# Python graph (already running on :2024):
pkill -9 -f "langgraph dev"; setsid nohup langgraph dev > /tmp/opencode/langgraph-dev.log 2>&1 < /dev/null & disown

# Next.js UI (already running on :3000):
cd ui && npm run dev:frontend
```

Open **http://localhost:3000**. The browser proxies `/api/*` to the graph.

---

## 4. The extension recipes

### 4.1 Add a new function / tool / node to the graph

**UI changes: none.** As long as your node still writes `final_answer` /
`generated_medical_output` / `retrieved_chunks`, the UI renders it
automatically. Restart the graph server, smoke-test with the SDK, done.

### 4.2 Display a NEW graph output field

If you add e.g. `memory_summary` or `confidence_score` to the graph state,
three precise spots (≈10 minutes):

```ts
// 1. assistant.tsx — extend the type
export type GroundedMetadata = {
  answerText: string;
  retrievedChunks: string[];
  status?: string;
  generatedOutputValid?: string;
  memorySummary?: string;        // new
};

// 2. assistant.tsx — capture it in `stream` (same pattern as status):
if (typeof values.memory_summary === "string") {
  metadata.memorySummary = values.memory_summary;
}

// 3. grounded-message.tsx — render it after <MessagePrimitive.Parts>:
{/* e.g. <p>{metadata?.memorySummary}</p> */}
```

Also mirror the field in the `load` path (`getState` typing + reconstruction)
if it should survive a page refresh.

### 4.3 Add memory — DIY guide (recommended: you implement this)

Goal: threads survive page refreshes. Two layers involved.

**Layer A — graph-side checkpointer.** The graph must be compiled with a
checkpointer so thread state is persisted server-side:

```python
# src/agent.py — near the bottom, replacing:
#   app = graph.compile()
from langgraph.checkpoint.memory import InMemorySaver
app = graph.compile(checkpointer=InMemorySaver())
```

- `InMemorySaver()` = in-memory only; threads survive for the lifetime of the
  graph server process (page refreshes included). Lost on server restart.
- For durability across restarts use a disk-backed saver, e.g.
  `langgraph-checkpoint-sqlite` (`SqliteSaver`) or Postgres. InMemorySaver is
  the minimal first step.
- Then restart the graph server so the new compiled app is loaded.

**Layer B — UI-side thread tracking.** The UI currently creates a *new*
thread per turn inside `stream`, but `load()` only knows the `create()`-thread
(which is empty). For history to reload after a refresh, the UI must remember
which per-turn threads belong to the conversation. Options:

1. Minimal: keep a module-level `Map<externalId, threadId[]>`; on `load`,
   read the last thread id from the map and call
   `client.threads.getState(lastThreadId)`. Works within one browser session.
2. Durable: persist the mapping in `localStorage` keyed by the UI thread id,
   so a full page reload can reconstruct history from the stored thread ids.
   (This is the part that makes "threads not lost" real across refreshes.)

The graph's `Feedback`/`messages` accumulation means you should **not** just
reuse one thread for all turns unless the agent's feedback branch is also
fixed graph-side — that was the original multi-turn context-bleed bug.

### 4.4 New UI feature (thread sidebar, follow-up chips, auth)

Standard assistant-ui patterns. Add components under
`ui/components/assistant-ui/`, register via `Thread components={{ ... }}` in
`assistant.tsx`. No graph changes required.

---

## 5. Loading / streaming UX (current implementation)

Latency reality: a medical query makes several sequential LLM round-trips
(router → medical agent → retrieval tool → checker → synthesizer). The graph
emits `values` events only after each node finishes, so the browser sees
nothing for tens of seconds. `composer-header.tsx` addresses this:

- **`ThreadComposerHeader`** — always-visible agent identity row above the
  composer: name + live status pill (`Ready` / pulsing `Working`). Pinned
  above the text box per product request.
- **`StreamingStatus`** — rotating, fading status lines shown while a run is
  in flight (`Routing…` → `Searching clinical evidence…` → `Verifying each
  claim…` → `Synthesizing…`), each fading in for ~4.5s. Pure client-side
  rotation — zero extra graph traffic, honest ("working", not fake progress).

Both components read `s.thread.isRunning` / `s.thread.isLoading` /
`messages.length` via `useAuiState` (primitives only — never derive fresh
arrays in selectors; see §7).

---

## 6. The verification loop

```
Python change  ->  restart langgraph dev  ->  curl/SDK smoke test  ->  browser test at :3000
UI change      ->  npx tsc --noEmit (must exit 0)                ->  browser test
```

- SDK smoke test: `curl http://localhost:2024/info`, then a run via the proxy.
- After UI edits always `cd ui && npx tsc --noEmit`.
- Browser E2E: check 0 console errors, refusal banner only on ungrounded
  answers, sources collapsible, second turn answers the *new* question.

---

## 7. Known traps (from the bug log)

- **Never return fresh arrays from `useAuiState` selectors.** React's
  `useSyncExternalStore` throws "getSnapshot should be cached" and the hook
  yields `undefined` → `reading 'map'` crash. Return a primitive or stable
  reference only.
- **In-flight messages carry `metadata: { custom: {} }`.** Always guard
  field-wise: `(metadata?.retrievedChunks ?? []).map(...)`, not
  `metadata.retrievedChunks.map(...)`.
- **`messages: []` does not clear graph state.** MessagesState `add_messages`
  appends; the agent's `Feedback` branch re-answers stale turns. Fresh
  thread-per-turn sidesteps both.
- **Server lifecycle:** `pkill -9 -f "langgraph dev"` can hang if the shell
  matches its own command line; use `setsid nohup … < /dev/null & disown` for
  both servers or they die when the shell command times out.

---

## 8. Latency audit (measurements)

Audit date: 2026-08-08, against the running dev server (Bedrock
`global.anthropic.claude-haiku-4-5-20251001-v1:0`, Qdrant local, dev server
worker pool = 1). All timings are real measured values; **no code was
changed** for this audit.

### Measured latencies

| Path | Cold (after ≥4 min idle) | Warm (back-to-back) |
|---|---|---|
| Standard (conversational) | **128.6s** (server log, run `019fe276`) | 3.6–8.7s |
| RAG (medical) | **146.2s** (server log, run `019fe270`) | 18.6–27s |

### Per-stage warm timings (fresh process, sequential)

| Stage | Time | Note |
|---|---|---|
| Router (1 structured Haiku call) | 2.45s | `query_validator` |
| Standard agent (1 plain call) | 3.33s | `standard_agent` |
| Retrieval (MedEmbed embed + Qdrant) | 4.34s | local, once warmed |
| Medical agent (create_agent tool loop) | 7.71s | several model calls |
| Checker (1 structured call) | 2.58s | `checker` |
| Synthesizer (1 plain call) | 1.72s | `synthesizer` |

### Root causes (ranked)

1. **Cold start of the Bedrock call after idle — the dominant cost.** The
   server log shows the exact pattern: after ≥4 min of idle, the *first*
   Bedrock Converse call in a run takes **~64s** (router alone), then every
   subsequent call drops to 2–5s. The user's 128.6s / 146.2s runs were both
   preceded by idle gaps; every warm run is 3–27s. Contributing factors:
   cross-region `global.` inference-profile routing, connection re-establish
   after idle, and the module-level boto3 client re-validating state.
2. **Sequential LLM round-trips — the architectural floor.** The medical
   path serializes ≥5 model calls (router → medical_agent tool loop → checker
   → synthesizer), ~20–27s even warm. The standard path needs only 2 calls
   (~5–8s warm).
3. **HuggingFace cache re-validation on the embedding model.** 96 HF
   HEAD/GET requests logged; each retrieval can incur network checks against
   huggingface.co (worse on cold boot, offline environments, or first use).
4. **Dev-server worker pool = 1.** `langgraph dev` shows `max=1` /
   `multitask_strategy=enqueue` — concurrent users queue behind each other.
5. **No token streaming.** The UI receives `values` events only after nodes
   finish; the browser sees a blank viewport for the whole run.

### Mitigations (not yet applied — decision needed)

1. **Warm-up ping on boot** (highest ROI): after the graph server starts,
   fire one tiny Bedrock invoke + one retrieval so the first user query never
   pays the ~64s cold start. Kills the dominant cost outright.
2. **Region-pinned model ID**: drop the `global.` inference-profile prefix
   when the deployment region is fixed (us-east-1) to avoid cross-region
   routing cold starts. Trade-off: lose cross-region capacity routing.
3. **Collapse sequential calls**: skip the router for obvious medical
   queries, force a single retrieval via `tool_choice`, tighten
   `Response_route` retries. Warm RAG could drop from ~27s toward ~12–15s.
4. **Enable token streaming** (Bedrock streaming + `messages/partial`
   events): perceived latency collapses even if wall-clock stays similar —
   pairs with the `StreamingStatus` indicator already in the UI.
5. **Cache the HF model offline**: `HF_HUB_OFFLINE=1` after first load, or
   pin the local snapshot, to eliminate per-run HF network checks.
6. **Production server** (`langgraph up` / platform) instead of the dev
   worker pool of 1 for anything multi-user.
7. **Parallelize router + retrieval**: the chunks don't depend on the
   router's verdict — fetch while routing. More invasive; defer.
