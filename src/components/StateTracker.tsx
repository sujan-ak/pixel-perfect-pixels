import { motion } from "framer-motion";
import { Check } from "lucide-react";
import { STATES, type IncidentState } from "@/lib/aurashield/types";
import { cn } from "@/lib/utils";

const ACTIVE_TONE: Record<string, string> = {
  OBSERVED: "warning",
  CANDIDATE: "warning",
  VERIFIED: "success",
  RESPONSE_PROPOSED: "critical",
  OPERATOR_APPROVED: "success",
  COORDINATION_IN_PROGRESS: "warning",
  ACKNOWLEDGED: "success",
  CLOSED: "success",
  REJECTED: "critical",
};

function toneClasses(tone: string) {
  if (tone === "success") return "border-success text-success glow-success";
  if (tone === "critical") return "border-critical text-critical glow-critical";
  return "border-warning text-warning glow-warning";
}

export function StateTracker({ state }: { state: IncidentState | null }) {
  const rejected = state === "REJECTED";
  const currentIndex = state && !rejected ? STATES.indexOf(state as (typeof STATES)[number]) : -1;

  return (
    <div className="panel p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[11px] tracking-[0.2em] text-muted-foreground">
          STATE MACHINE
        </span>
        {rejected && (
          <span className="rounded-md border border-critical px-2 py-0.5 font-mono text-[11px] text-critical glow-critical">
            REJECTED — CHAIN HALTED
          </span>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {STATES.map((s, i) => {
          const isPast = currentIndex > i;
          const isCurrent = currentIndex === i;
          const tone = ACTIVE_TONE[s] ?? "warning";
          return (
            <motion.div
              key={s}
              animate={isCurrent ? { opacity: [1, 0.72, 1] } : { opacity: 1 }}
              transition={{ duration: 1.8, repeat: isCurrent ? Infinity : 0, ease: "easeInOut" }}
              className={cn(
                "flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 font-mono text-[10px] tracking-wider transition-colors sm:text-[11px]",
                isCurrent
                  ? toneClasses(rejected ? "critical" : tone)
                  : isPast
                    ? "border-success/40 text-success/70"
                    : "border-border text-neutral",
              )}
            >
              {isPast && <Check className="h-3 w-3" />}
              {s}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
