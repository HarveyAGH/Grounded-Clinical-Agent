"use client";

import { useAuiState } from "@assistant-ui/react";
import { useEffect, useState, type FC } from "react";
import {
  ActivityIcon,
  LoaderCircleIcon,
  SearchIcon,
  ShieldCheckIcon,
  SparklesIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Rotating status lines shown above the composer while a run is in flight.
 * The graph streams `values` events only after each node finishes, and a
 * full medical query takes several sequential LLM round-trips (router ->
 * agent -> tool -> checker -> synthesizer), so the user would otherwise
 * stare at a static screen for minutes. Fading text rotation masks that
 * latency cheaply and honestly ("working", not fake progress bars).
 */
const STATUS_STEPS = [
  { text: "Routing your question\u2026", Icon: SparklesIcon },
  { text: "Searching clinical evidence\u2026", Icon: SearchIcon },
  { text: "Verifying each claim against the sources\u2026", Icon: ShieldCheckIcon },
  { text: "Synthesizing the grounded answer\u2026", Icon: ActivityIcon },
] as const;

const ROTATE_MS = 4500;

export const StreamingStatus: FC = () => {
  const isRunning = useAuiState((s) => s.thread.isRunning);
  const hasMessages = useAuiState((s) => s.thread.messages.length > 0);
  const isLoading = useAuiState((s) => s.thread.isLoading);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!isRunning || hasMessages === false || isLoading) return;
    const id = setInterval(
      () => setStep((s) => (s + 1) % STATUS_STEPS.length),
      ROTATE_MS,
    );
    return () => clearInterval(id);
  }, [isRunning, hasMessages, isLoading]);

  if (!isRunning || hasMessages === false || isLoading) return null;

  const { text, Icon } = STATUS_STEPS[step];

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center justify-center gap-2 px-4 py-1"
    >
      <LoaderCircleIcon className="text-muted-foreground size-4 animate-spin" />
      <span
        key={step}
        className="animate-in fade-in slide-in-from-bottom-0.5 fill-mode-both text-muted-foreground flex items-center gap-1.5 text-xs duration-500"
      >
        <Icon className="text-muted-foreground/70 size-3.5" />
        {text}
      </span>
    </div>
  );
};

/**
 * Agent identity row pinned above the text box: name + live status pill.
 * Always visible (new-chat and threaded views) so the product never reads
 * as an anonymous input.
 */
export const ThreadComposerHeader: FC = () => {
  const isRunning = useAuiState((s) => s.thread.isRunning);

  return (
    <div className="flex flex-col items-center gap-1.5 px-4">
      <div className="flex items-center gap-2">
        <div className="bg-primary/10 text-primary flex size-6 items-center justify-center rounded-full">
          <ActivityIcon className="size-3.5" />
        </div>
        <span className="text-foreground text-sm font-medium">
          Grounded Clinical Agent
        </span>
        <span
          className={cn(
            "text-muted-foreground flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium tracking-wide uppercase",
            isRunning &&
              "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
          )}
        >
          <span
            className={cn(
              "size-1.5 rounded-full",
              isRunning ? "animate-pulse bg-emerald-500" : "bg-muted-foreground/40",
            )}
          />
          {isRunning ? "Working" : "Ready"}
        </span>
      </div>
      <p className="text-muted-foreground text-center text-[11px]">
        Answers only from retrieved clinical evidence — refuses to guess
      </p>
    </div>
  );
};
