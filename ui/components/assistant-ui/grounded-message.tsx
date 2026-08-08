"use client";

import { MessagePrimitive } from "@assistant-ui/react";
import { useAuiState } from "@assistant-ui/store";
import { type FC, useState } from "react";
import { BookOpenIcon, ShieldAlertIcon } from "lucide-react";

import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import type { GroundedMetadata } from "@/app/assistant";

const REFUSAL_MARKERS = [
  "cannot answer",
  "can't answer",
  "not able to answer",
  "unable to answer",
  "no evidence",
  "does not provide",
  "cannot provide",
  "not in the retrieved",
  "not covered by the retrieved",
  "does not contain specific",
  "no specific guidelines",
  "does not address",
  "do not address",
  "cannot be determined",
  "no information is available",
  "I cannot",
  "I can't",
  "I am not able",
  "I'm not able",
  "escalated for human review",
  "could not complete",
];

const isRefusal = (text: string, metadata?: GroundedMetadata) => {
  if (metadata?.status === "escalated") return true;
  const lower = text.toLowerCase();
  return REFUSAL_MARKERS.some((m) => lower.includes(m));
};

type SourceBlock = {
  label: string;
  body: string;
};

const parseChunk = (chunk: string, index: number): SourceBlock => {
  const match = chunk.match(/^\[(Source \d+: [^\]]+)\]\n?/);
  if (match) {
    return { label: match[1], body: chunk.slice(match[0].length) };
  }
  return { label: `Source ${index + 1}`, body: chunk };
};

const SourceItem: FC<{ source: SourceBlock }> = ({ source }) => {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="border-border/60 dark:border-muted-foreground/15 rounded-lg border"
    >
      <CollapsibleTrigger className="hover:bg-muted/50 flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs transition-colors">
        <span className="text-foreground font-medium truncate">{source.label}</span>
        <span className="text-muted-foreground shrink-0">{open ? "Hide" : "Show"} chunk</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="text-muted-foreground border-border/40 border-t px-3 py-2 text-[13px] leading-relaxed whitespace-pre-wrap">
        {source.body}
      </CollapsibleContent>
    </Collapsible>
  );
};

export const GroundedAssistantMessage: FC = () => {
  const metadata = useAuiState(
    (s) => s.message?.metadata?.custom,
  ) as GroundedMetadata | undefined;

  const isStreaming = useAuiState(
    (s) => s.message?.isLast === true && s.thread.isRunning === true,
  );

  const fullText = metadata?.answerText ?? "";

  // Suppress the banner while this message is still streaming: partial token
  // chunks can transiently match refusal markers (e.g. "I cannot") before the
  // complete answer lands, which would flash a false refusal card.
  const refusal =
    metadata !== undefined && !isStreaming && isRefusal(fullText, metadata);

  const sources = (metadata?.retrievedChunks ?? []).map(parseChunk);

  return (
    <MessagePrimitive.Root
      data-slot="aui_assistant-message-root"
      data-role="assistant"
      className="fade-in slide-in-from-bottom-1 animate-in relative -mb-7.5 pb-7.5 duration-150 [contain-intrinsic-size:auto_200px] [content-visibility:auto]"
    >
      <div
        data-slot="aui_assistant-message-content"
        className={cn(
          "text-foreground px-2 leading-relaxed wrap-break-word",
          refusal && "border-border/40 bg-muted/30 rounded-xl border px-4 py-3",
        )}
      >
        {refusal && (
          <div className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400 mb-3 flex items-start gap-2 rounded-lg border px-3 py-2 text-sm">
            <ShieldAlertIcon className="mt-0.5 size-4 shrink-0" />
            <div>
              <p className="font-medium">Not answered from the evidence</p>
              <p className="text-muted-foreground text-xs">
                The agent could not ground this answer in the retrieved clinical
                sources, so it refused rather than guess.
              </p>
            </div>
          </div>
        )}

        <MessagePrimitive.Parts>
          {({ part }) => {
            if (part.type === "text") return <MarkdownText />;
            return null;
          }}
        </MessagePrimitive.Parts>

        {sources.length > 0 && (
          <div className="mt-4 flex flex-col gap-1.5">
            <div className="text-muted-foreground flex items-center gap-1.5 text-xs font-medium">
              <BookOpenIcon className="size-3.5" />
              Sources
            </div>
            {sources.map((source, i) => (
              <SourceItem key={i} source={source} />
            ))}
          </div>
        )}
      </div>
    </MessagePrimitive.Root>
  );
};
