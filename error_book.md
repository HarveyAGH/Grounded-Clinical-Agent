# Some of the errors and their fixes that i did:
1. First error:

for the While loop i kept coding it like this = if user_input.lower() == ["exit"]: break

* error: the user_input is a string, and we are comparing that to a list, a string can never be compared to a list, we should replace "==" with "in"


2. Second error: `Evaluator Confusion`
   On a Generated output that uses a MedicalAnswer Structured output showcasing the full answer alongside the citations, it have occured that some of the citation's returned a risky note claiming that 40% of the generated response did not match the retrieved chunks even tho the verdict was set to `is_tracable`

* Mitigation:
    Problem was solved due to the ordering inside the Evaluator Structured output, at first it was ordered by choosing a Verdict first and only THEN responds with a feedback, whereas logically it should've respond with a feedback understanding the comparisons, and only then provides a verdict


3. Third error: `The baseline that meant nothing (r000)`
   When i first ran the eval i got a 0.063 faithfulness score which looked like a total disaster. Before panicking about the agent being garbage, i checked WHY. Turned out the ragas import was silently broken and the code fell back to a token-overlap heuristic — so it was never actually measuring faithfulness, it was measuring how many words the answer happened to share with the chunks.

* Lesson: a metric is worthless if you don't know what's underneath it. I tagged that run as INVALID in the ledger instead of treating it as a real result, then fixed the import so the real judge (Sonnet 4.6) actually runs.


4. Fourth error: `Route() returning None (KeyError)`
   The graph would crash with a KeyError on some queries. The Router returned a status like "medical_agent", but the Route() function only had a mapping for "medical_agent" and a nonexistent "non_medical_basic_agent" — so anything else fell through and returned None, and LangGraph blew up.

* Fix: made Route() a catch-all — anything that isn't "medical_agent" goes to the standard conversation agent. The router can never return None again.


5. Fifth error: `Judge auth failure (NoAuthTokenError)`
   The judge model threw an auth error even though the agent worked fine. Turned out load_dotenv() was being called AFTER the judge LLM was constructed at module import — so when the LLM was built, the bearer token from .env wasn't loaded yet.

* Fix: moved load_dotenv() to the very top of the module, before anything touches the LLM. Order of imports/init matters when you read env vars.


6. Sixth error: `Judge model not found (ValidationException)`
   After fixing auth, the judge still failed because the model ID was wrong. The agent worked because its BEDROCK_MODEL_ID had the "global." prefix (inference profile), but the judge's default ID didn't.

* Fix: added JUDGE_MODEL_ID=global.anthropic.claude-sonnet-4-6 to .env, same global. prefix pattern. Lesson: on this setup every model ID needs the global. prefix, not just the ones that happen to work.


7. Seventh error: `Router prompt routing everything to chat`
   After fixing the crash, tons of medical questions got scored 0 — the answers were coming back as empty. Root cause: the router system prompt had an "always route to conversation agent" line and still mentioned a web-search agent that didn't even exist in the graph. So the router kept sending medical stuff to the wrong place.

* Fix: rewrote src/prompts/AgentDecisionSystemPrompt.md to only describe the two agents that actually exist (medical_agent and conversational_agent) and removed the broken "always route to chat" instruction. Also removed "web_search" from the Router verdict schema since that agent no longer exists. Lesson: the prompt and the code must describe the same world — stale agents in a prompt cause real routing failures.


8. Eighth error: `Intermittent medical agent parse crash`
   Sometimes the medical agent would crash with a StructuredOutputValidationError — the model occasionally returns empty content and the structured output can't parse it. It wasn't deterministic, which made it nasty to debug.

* Fix: wrapped the invoke in a 3-attempt retry loop that only re-invokes on that specific validation error, and re-raises if all 3 fail. Flaky model output needs a retry, not a code rewrite.


9. Ninth error: `Checker was punishing refusals (halluc_13 loop)`
   Questions like "prescribe me a fluoride toothpaste" would loop forever and escalate even though the agent was doing the RIGHT thing — refusing. The checker was flagging disclaimers and "I can't prescribe" statements as untraceable claims, which made the REDO loop spin until it gave up.

* Fix: updated the groundness_checker system prompt AND the grader description in the EvaluatorOptimizer schema to explicitly exclude refusal/disclaimer/absence statements from traceability checking. Only substantive medical claims get checked now. halluc_13 went from 0.0 to passing cleanly after this.


10. Tenth error: `The checker caught a REAL hallucination (halluc_10/12)`
   After fixing the refusals, halluc_10 and halluc_12 still failed — but for the opposite reason. The agent was inventing claims the corpus doesn't support: "the ADA recommends NSAIDs as first-line" when no retrieved chunk mentions ADA, and "any lesion should be evaluated by a dentist" when no chunk says that. The checker was RIGHT to fail them.

* Lesson: this is the eval working as intended. The failure moved from the checker to the agent — the agent needs to stop citing sources (ADA) and clinical guidance that aren't in the retrieved chunks. That's the next fix target, not the checker.


11. Eleventh error: `Eval harness reading the wrong field (halluc_14)`
   "What's the capital of France?" scored 0 with an EMPTY output — but the agent actually answered correctly ("Paris"). The problem: the conversation agent writes to generated_normal_output, while the eval only read generated_medical_output. So valid conversational answers were being scored as if nothing happened.

* Fix: run_eval.py now reads whichever output field actually ran. And since out-of-domain queries produce no medical claims, they're scored 1.0 — nothing was hallucinated, so it's not a failure. Also recorded a "routed" field per question so future runs are auditable.


12. Twelfth error: `Fabricated precision (halluc_17)`
   Question asked for the edentulism rate in 2010 per CDC. Agent answered "19.7%" — a nice precise number, scored 0. Because the corpus says "nearly 1 in 5 adults aged 75+", not "19.7%". The agent converted an imprecise source statement into a fabricated precise number.

* Lesson: hallucination isn't only invented sources — inventing PRECISION is also hallucination. An answer that's directionally right but adds exact numbers the corpus never stated is untraceable. The agent should stick to the corpus's own wording.



-------------------------------------------------------------------------------
13. Thirteenth error: `Prompt file refactor that killed the import`
   Moved the medical agent system prompt out of the inline string (where it had the missing-spaces bug) into its own file for cleanliness. Clean idea — but the code referenced `src/prompts/MedicalAgentSystemPrompt.md` while the actual file was named `src/prompts/MedicalSystemMessage.md`. The whole module died with `FileNotFoundError` on import — nothing could run, not even the eval.

* Mitigation / how i fixed it:
    Checked the reference in src/agent.py against what actually existed in src/prompts/, spotted the mismatch, and fixed the path to point at the real file. Verified with a clean import before touching anything else.
* Lesson: a refactor that touches file paths needs a compile/import check right after, not later. The crash happened at import time, which is the cheapest possible failure — it could have been caught the second the refactor landed. Also: naming two prompt files one letter apart (MedicalSystemMessage vs MedicalAgentSystemPrompt) is asking for this exact mistake.


-------------------------------------------------------------------------------
14. Fourteenth error: `The temporal bait I misdiagnosed (halluc_17, round 2)`
   I had written "19.7%" off as fabricated precision and told the user the corpus only says "nearly 1 in 5". The sanity check proved me wrong: the CDC chunk EXPLICITLY states "The prevalence of edentulism among adults increased from 1.2% at 35-49 years to 5.9% at 50-64 years, 11.4% at 65-74 years, and 19.7% at 75 years or older." So 19.7% IS in the corpus — the actual trap was the question's "in 2010" framing. The agent cited a real, age-specific number but as if it answered the 2010 question, and the checker correctly failed the temporal mismatch.

* Mitigation / how i fixed it:
    Verified the claim against the actual retrieved chunk text instead of trusting my memory of the corpus. Once grounded, halluc_17 now passes (`claim_is_tracable`) with the new grounding prompts.
* Lesson: NEVER diagnose a hallucination from memory of what you think the corpus says — open the chunk. "The corpus doesn't say X" is a claim that needs evidence just like the agent's claims do. Also: temporal bait questions are about the answer matching the ASKED timeframe, not just matching the corpus.


-------------------------------------------------------------------------------
15. Fifteenth error: `The flaky pass (halluc_10 and halluc_12)`
   After the grounding-prompt fixes, the sanity check showed both questions pass on some runs and escalate on others (roughly 50/50). Same input, different outcome run to run.

* Mitigation / how i fixed it:
    Ran each question twice and compared. The escalations are no longer deterministic — the ADA hallucination and the invented "see a dentist" guidance are gone from the outputs. What remains is normal LLM nondeterminism: sometimes the agent keeps one extra unsupported clause and the checker catches it, sometimes it doesn't. The checker is doing its job either way.
* Lesson: distinguish "always fails" from "sometimes fails". A deterministic failure is a bug in your logic/prompt. A stochastic failure at ~50% is model variance — you don't fix that by rewiring the graph, you fix it by nudging the prompt (done) or accepting it as noise in the eval. Also, run flaky questions more than once before declaring victory or defeat.
