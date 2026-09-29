import { motion } from "framer-motion";
import { Check, CornerDownRight, Smartphone, XCircle } from "lucide-react";
import { STATES, type Incident, type IncidentState } from "@/lib/aurashield/types";

const SHORT_LABELS: Record<string, string> = {
  OBSERVED: "Observed",
  CANDIDATE: "Candidate",
  VERIFIED: "Verified",
  RESPONSE_PROPOSED: "Proposed",
  OPERATOR_APPROVED: "Approved",
  COORDINATION_IN_PROGRESS: "Dispatch",
  ACKNOWLEDGED: "Ack'd",
  EN_ROUTE: "En Route",
  ON_SCENE: "On Scene",
  HANDED_OVER: "Handover",
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
  ACKNOWLEDGED: "Acknowledged by responder",
  EN_ROUTE: "Ambulance en route",
  ON_SCENE: "Ambulance arrived on scene",
  HANDED_OVER: "Patient handed over at hospital",
  CLOSED: "Incident closed",
  REJECTED: "Rejected",
};

export function StateTracker({
  state,
  incident,
}: {
  state: IncidentState | null;
  incident?: Incident | null;
}) {
  const isRejected = state === "REJECTED";
  const currentIndex = state && !isRejected ? STATES.indexOf(state as (typeof STATES)[number]) : -1;
  const candidateIndex = STATES.indexOf("CANDIDATE");

  const phase1States = STATES.slice(0, 6); // OBSERVED -> COORDINATION_IN_PROGRESS
  const phase2States = STATES.slice(6); // ACKNOWLEDGED -> CLOSED

  const renderStateCell = (s: (typeof STATES)[number], idx: number) => {
    const isPast = !isRejected && currentIndex > idx;
    const isCurrent = !isRejected && currentIndex === idx;
    const isPastBeforeReject = isRejected && idx <= candidateIndex;

    const activeColor =
      s === "OBSERVED" || s === "CANDIDATE"
        ? "border-signal-pending text-signal-pending bg-signal-pending/10"
        : s === "CLOSED"
          ? "border-signal-closed text-text-muted bg-signal-closed/10"
          : s === "ACKNOWLEDGED" || s === "EN_ROUTE" || s === "ON_SCENE" || s === "HANDED_OVER"
            ? "border-emerald-500 text-emerald-400 bg-emerald-500/10"
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
                    : s === "CLOSED"
                      ? "bg-signal-closed"
                      : "bg-signal-verified animate-pulse"
                  : "bg-line"
              }`}
            />
          )}
        </div>

        <span className="truncate w-full text-center leading-tight">{SHORT_LABELS[s] ?? s}</span>
      </motion.div>
    );
  };

  return (
    <div className="rounded border border-line bg-bg-panel p-3.5 space-y-2.5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-line pb-2">
        <div className="flex items-center gap-2">
          <span className="font-sans text-panel-header text-text-primary">State machine</span>
          <span className="font-sans text-label text-text-muted">/ sequential safety rail</span>
        </div>
        {isRejected ? (
          <span className="rounded border border-signal-rejected bg-signal-rejected/10 px-2 py-0.5 font-sans text-label font-medium text-signal-rejected">
            Halted &mdash; verification rejected
          </span>
        ) : state ? (
          <div className="flex items-center gap-2">
            {incident?.responder_id && (
              <span className="flex items-center gap-1 rounded border border-emerald-500/40 bg-emerald-500/10 px-1.5 py-0.5 font-sans text-[10px] text-emerald-400">
                <Smartphone className="h-3 w-3" />
                {incident.responder_id}
              </span>
            )}
            <span className="rounded border border-line bg-bg-panel-raised px-2 py-0.5 font-sans text-label text-text-muted">
              Active:{" "}
              <span className="text-text-primary font-medium">{FULL_LABELS[state] ?? state}</span>
            </span>
          </div>
        ) : (
          <span className="font-sans text-label text-text-muted">
            Standby &mdash; no active sequence
          </span>
        )}
      </div>

      {/* Phase 1: Detection & Dispatch */}
      <div>
        <div className="text-[10px] uppercase tracking-wider text-text-muted/70 font-semibold mb-1">
          1. Verification &amp; Clearance
        </div>
        <div className="grid grid-cols-6 gap-1">
          {phase1States.map((s, idx) => renderStateCell(s, idx))}
        </div>
      </div>

      {/* Phase 2: Mobile Responder Telemetry & Handoff */}
      <div>
        <div className="text-[10px] uppercase tracking-wider text-text-muted/70 font-semibold mb-1 flex items-center justify-between">
          <span>2. Mobile Responder Telemetry</span>
          {incident?.field_status && (
            <span className="text-emerald-400 font-bold lowercase">
              • {incident.field_status.replace("_", " ")}
            </span>
          )}
        </div>
        <div className="grid grid-cols-5 gap-1">
          {phase2States.map((s, idx) => renderStateCell(s, idx + 6))}
        </div>
      </div>

      {/* Divergent Branch for REJECTED state */}
      <div className="flex items-center justify-between border-t border-line/60 pt-2 font-sans text-label">
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
