import { motion } from "framer-motion";
import { Check, CornerDownRight, XCircle } from "lucide-react";
import { STATES, type IncidentState } from "@/lib/aurashield/types";

const SHORT_LABELS: Record<string, string> = {
  OBSERVED: "Observed",
  CANDIDATE: "Candidate",
  VERIFIED: "Verified",
  RESPONSE_PROPOSED: "Proposed",
  OPERATOR_APPROVED: "Approved",
  COORDINATION_IN_PROGRESS: "Dispatch",
  ACKNOWLEDGED: "Ack'd",
  CLOSED: "Closed",
  REJECTED: "Rejected",
};

const FULL_LABELS: Record<string, string> = {
  OBSERVED: "Observed",
  CANDIDATE: "Candidate",
  VERIFIED: "Verified",
  RESPONSE_PROPOSED: "Response proposed",
  OPERATOR_APPROVED: "Operator approved",
  COORDINATION_IN_PROGRESS: "Coordination in progress",
  ACKNOWLEDGED: "Acknowledged",
  CLOSED: "Closed",
  REJECTED: "Rejected",
};

export function StateTracker({ state }: { state: IncidentState | null }) {
  const isRejected = state === "REJECTED";
  const currentIndex = state && !isRejected ? STATES.indexOf(state as (typeof STATES)[number]) : -1;
  const candidateIndex = STATES.indexOf("CANDIDATE");

  return (
    <div className="rounded border border-line bg-bg-panel p-3.5">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between border-b border-line pb-2">
        <div className="flex items-center gap-2">
          <span className="font-sans text-panel-header text-text-primary">State machine</span>
          <span className="font-sans text-label text-text-muted">/ sequential safety rail</span>
        </div>
        {isRejected ? (
          <span className="rounded border border-signal-rejected bg-signal-rejected/10 px-2 py-0.5 font-sans text-label font-medium text-signal-rejected">
            Halted &mdash; verification rejected
          </span>
        ) : state ? (
          <span className="rounded border border-line bg-bg-panel-raised px-2 py-0.5 font-sans text-label text-text-muted">
            Active: <span className="text-text-primary font-medium">{FULL_LABELS[state] ?? state}</span>
          </span>
        ) : (
          <span className="font-sans text-label text-text-muted">Standby &mdash; no active sequence</span>
        )}
      </div>

      {/* Main 8-State Horizontal Rail - Clean compact layout without scrollbar */}
      <div className="grid grid-cols-8 gap-1 py-1">
        {STATES.map((s, idx) => {
          const isPast = !isRejected && currentIndex > idx;
          const isCurrent = !isRejected && currentIndex === idx;
          const isPastBeforeReject = isRejected && idx <= candidateIndex;

          const activeColor =
            s === "OBSERVED" || s === "CANDIDATE"
              ? "border-signal-pending text-signal-pending bg-signal-pending/10"
              : "border-signal-verified text-signal-verified bg-signal-verified/10";

          return (
            <motion.div
              key={s}
              title={FULL_LABELS[s]}
              className={`relative flex flex-col items-center justify-center rounded border py-1.5 px-1 font-sans text-[11px] font-medium transition-colors text-center ${
                isCurrent
                  ? `${activeColor} ring-1 ring-current`
                  : isPast || isPastBeforeReject
                  ? "border-signal-verified/40 bg-signal-verified/5 text-signal-verified"
                  : "border-line bg-bg-void text-text-muted/60"
              }`}
              animate={isCurrent ? { scale: [1, 1.03, 1] } : { scale: 1 }}
              transition={{ duration: 0.2 }}
            >
              {/* Orchestrated transition glow moment */}
              {isCurrent && (
                <motion.div
                  layoutId="state-rail-active-glow"
                  className="absolute inset-0 rounded bg-current opacity-15 pointer-events-none"
                  transition={{ duration: 0.2, ease: "easeInOut" }}
                />
              )}

              <div className="flex items-center gap-1 mb-0.5">
                {isPast || isPastBeforeReject ? (
                  <Check className="h-3 w-3 shrink-0 text-signal-verified" />
                ) : (
                  <span
                    className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                      isCurrent
                        ? s === "OBSERVED" || s === "CANDIDATE"
                          ? "bg-signal-pending animate-pulse"
                          : "bg-signal-verified animate-pulse"
                        : "bg-line"
                    }`}
                  />
                )}
              </div>

              <span className="truncate w-full text-center leading-tight">
                {SHORT_LABELS[s] ?? s}
              </span>
            </motion.div>
          );
        })}
      </div>

      {/* Divergent Branch for REJECTED state */}
      <div className="mt-2.5 flex items-center justify-between border-t border-line/60 pt-2 font-sans text-label">
        <div className="flex items-center text-text-muted">
          <CornerDownRight className="h-3.5 w-3.5 text-text-muted mr-1.5" />
          <span>Divergent branch:</span>
        </div>
        <div
          className={`flex items-center gap-1.5 rounded border px-2.5 py-0.5 font-medium ${
            isRejected
              ? "border-signal-rejected bg-signal-rejected/15 text-signal-rejected ring-1 ring-signal-rejected"
              : "border-line bg-bg-void text-text-muted/60"
          }`}
        >
          {isRejected ? (
            <XCircle className="h-3.5 w-3.5 text-signal-rejected shrink-0" />
          ) : (
            <span className="h-1.5 w-1.5 rounded-full bg-line shrink-0" />
          )}
          <span>Rejected (Candidate &rarr; anomaly)</span>
        </div>
      </div>
    </div>
  );
}
