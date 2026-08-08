"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import {
  useLangGraphRuntime,
  type LangChainMessage,
} from "@assistant-ui/react-langgraph";
import { useMemo } from "react";

import { GroundedAssistantMessage } from "@/components/assistant-ui/grounded-message";
import { Thread } from "@/components/assistant-ui/thread";
import { ASSISTANT_ID, createClient } from "@/lib/chatApi";

/**
 * Extra state captured from the graph's `values` events and attached to the
 * clean assistant message via `additional_kwargs.metadata`, so the message
 * component can render citations / refusal styling per-message without
 * touching the Python graph.
 */
export type GroundedMetadata = {
  answerText: string;
  retrievedChunks: string[];
  status?: string;
  generatedOutputValid?: string;
};

const CLEAN_MESSAGE_ID_PREFIX = "clean-answer-";

// Bedrock Converse streams message content as typed blocks
// ([{'type': 'text', 'text': ...}]), not plain strings. Extract text from
// either form so the delta-forwarding below can slice on characters.
function contentToText(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .map((block) =>
      typeof block === "string"
        ? block
        : block && typeof block === "object" && "text" in block
          ? String((block as { text: unknown }).text)
          : "",
    )
    .join("");
}

export function Assistant() {
  const client = useMemo(() => createClient(), []);

  const runtime = useLangGraphRuntime({
    unstable_allowCancellation: true,
    stream: async (messages, config) => {
      const { externalId } = await config.initialize();
      if (!externalId) throw new Error("Thread has not been initialized.");

      // The graph requires `user_query` at the TOP level of the state input.
      // Pull the latest user text out of the message history; do NOT send the
      // raw `messages` array (it contains tool-call JSON the UI must not see).
      const lastUserMessage = [...messages]
        .reverse()
        .find((m) => m.type === "human");
      const userQuery =
        typeof lastUserMessage?.content === "string"
          ? lastUserMessage.content
          : "";

      // Graph is single-turn: checkpointer accumulates `messages`/`Feedback`
      // across runs, so each user turn needs a fresh thread to avoid stale context.
      const { thread_id } = await client.threads.create();
      const run = client.runs.stream(thread_id, ASSISTANT_ID, {
        input: { user_query: userQuery },
        // "values" gives us full state snapshots (final_answer,
        // generated_medical_output, retrieved_chunks); "messages" streams the
        // LLM token chunks so the answer can render progressively.
        streamMode: ["values", "messages"],
        signal: config.abortSignal,
        onDisconnect: "cancel",
      });

      return (async function* () {
        // Stable id shared by every partial chunk and the final complete
        // message, so the accumulator merges them into ONE assistant message.
        const cleanId = `${CLEAN_MESSAGE_ID_PREFIX}${externalId}-${Date.now()}`;
        let cleanText: string | null = null;
        let metadata: GroundedMetadata = { answerText: "", retrievedChunks: [] };

        // SDK 1.9.x + server 0.12 emit v2 assistant-ui protocol events for
        // stream_mode "messages": "messages/partial" (accumulated text per
        // source message id), "messages/complete", "messages/metadata". Track
        // how much text we already forwarded per source id and only yield the
        // DELTA under cleanId, so appendLangChainChunk concatenates the
        // partials into ONE clean assistant message without duplicating text.
        const forwardedLenBySourceId = new Map<string, number>();

        for await (const event of run) {
          if (
            event.event === "messages/partial" ||
            event.event === "messages/complete"
          ) {
            const msgs = event.data as unknown[];
            for (const raw of msgs) {
              const msg = raw as {
                type?: string;
                content?: unknown;
                id?: string;
                tool_calls?: unknown[];
                tool_call_chunks?: unknown[];
              };
              // Forward only pure-text AI chunks (tool-call JSON must never
              // reach the UI), normalized to AIMessageChunk with our id so
              // appendLangChainChunk accumulates them into the clean message.
              const text = contentToText(msg.content);
              if (
                msg &&
                (msg.type === "ai" || msg.type === "AIMessageChunk") &&
                text.length > 0 &&
                !msg.tool_calls?.length &&
                !msg.tool_call_chunks?.length
              ) {
                const sourceId = msg.id ?? "";
                const forwarded = forwardedLenBySourceId.get(sourceId) ?? 0;
                const delta = text.slice(forwarded);
                if (delta.length > 0) {
                  forwardedLenBySourceId.set(sourceId, text.length);
                  yield {
                    event: "messages/partial" as const,
                    data: [
                      {
                        type: "AIMessageChunk",
                        id: cleanId,
                        content: delta,
                      },
                    ],
                  };
                }
              }
            }
            continue;
          }
          if (event.event !== "values") continue;
          const values = event.data as Record<string, unknown>;

          // Prefer the synthesizer's final_answer; fall back to the medical
          // output (also set by escalation nodes) or the conversational reply.
          const candidate =
            (values.final_answer as string | undefined) ??
            (values.generated_medical_output as string | undefined) ??
            (values.generated_normal_output as string | undefined);

          if (typeof candidate === "string" && candidate.trim()) {
            cleanText = candidate;
            metadata.answerText = candidate;
          }

          const chunks = values.retrieved_chunks;
          if (Array.isArray(chunks)) {
            metadata.retrievedChunks = chunks.map(String);
          }
          if (typeof values.status === "string") metadata.status = values.status;
          if (typeof values.generated_output_valid_or_not === "string") {
            metadata.generatedOutputValid =
              values.generated_output_valid_or_not;
          }
        }

        if (cleanText) {
          yield {
            event: "messages/complete" as const,
            data: [
              {
                type: "ai",
                id: cleanId,
                content: cleanText,
                additional_kwargs: { metadata },
              } satisfies LangChainMessage,
            ],
          };
        }      })();
    },
    create: async () => {
      const { thread_id } = await client.threads.create();
      return { externalId: thread_id };
    },
    load: async (externalId) => {
      const state = await client.threads.getState<{
        messages?: LangChainMessage[];
        final_answer?: string | null;
        generated_medical_output?: string | null;
        generated_normal_output?: string | null;
        retrieved_chunks?: unknown;
        status?: string;
        generated_output_valid_or_not?: string;
      }>(externalId);
      const values = state.values;

      // Graph contract: `messages` channel holds tool JSON; clean answer is in state values.
      const clean: LangChainMessage[] = (values.messages ?? []).filter(
        (m) => m.type === "human",
      );

      const answer =
        values.final_answer ??
        values.generated_medical_output ??
        values.generated_normal_output;

      if (typeof answer === "string" && answer.trim()) {
        const chunks = values.retrieved_chunks;
        clean.push({
          type: "ai",
          id: `${CLEAN_MESSAGE_ID_PREFIX}${externalId}-loaded`,
          content: answer,
          additional_kwargs: {
            metadata: {
              answerText: answer,
              retrievedChunks: Array.isArray(chunks) ? chunks.map(String) : [],
              status: values.status,
              generatedOutputValid: values.generated_output_valid_or_not,
            } satisfies GroundedMetadata,
          },
        });
      }

      return {
        messages: clean,
        interrupts: [],
      };
    },
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Thread components={{ AssistantMessage: GroundedAssistantMessage }} />
    </AssistantRuntimeProvider>
  );
}
