import { motion } from "framer-motion";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import type { Incident } from "@/lib/aurashield/types";

const FUSED_THRESHOLD = 0.35;
const CONFIDENCE_THRESHOLD = 0.8;
const MARGIN_THRESHOLD = 0.35;

export function AgentTugOfWar({ incident }: { incident: Incident | null }) {
  const corroborator = incident?.corroborator_score ?? 0;
  const skeptic = incident?.skeptic_score ?? 0;
  const fused = incident?.fused_score ?? 0;
  const margin = corroborator - skeptic;
  const total = corroborator + skeptic || 1;
  const pull = (corroborator / total) * 100;
  const thresholdMet = fused > FUSED_THRESHOLD && corroborator >= CONFIDENCE_THRESHOLD;

  return (
    <div className="flex h-full flex-col justify-between rounded border border-line bg-bg-panel p-4">
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-line pb-2.5">
        <div className="flex items-center gap-2">
          <span className="font-sans text-panel-header text-text-primary">Agent adjudication</span>
          <span className="font-sans text-label text-text-muted">/ dual-model fusion</span>
        </div>
        <span
          className={`rounded border px-2 py-0.5 font-sans text-label font-medium ${
            thresholdMet
              ? "border-signal-verified text-signal-verified bg-signal-verified/10"
              : "border-line text-text-muted bg-bg-panel-raised"
          }`}
        >
          {thresholdMet ? "Threshold met" : "Below threshold"}
        </span>
      </div>

      {/* Hero Score Display (32px IBM Plex Mono, cyan reserved for live WS data) */}
      <div className="my-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <ShieldCheck className="h-5 w-5 text-signal-verified" />
          <div>
            <div className="font-sans text-label text-text-muted">Corroborator</div>
            {/* Live WS streaming number in cyan signal-data */}
            <div className="font-mono text-xl font-semibold text-signal-data">
              {incident ? corroborator.toFixed(2) : "—"}
            </div>
          </div>
        </div>

        {/* Center Hero Number: 32px live fused score */}
        <div className="text-center">
          <div className="font-sans text-label text-text-muted">Fused score</div>
          <div className="font-mono text-hero-score font-semibold text-signal-data">
            {incident ? (fused > 0 ? `+${fused.toFixed(2)}` : fused.toFixed(2)) : "0.00"}
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="text-right">
            <div className="font-sans text-label text-text-muted">Skeptic</div>
            {/* Live WS streaming number in cyan signal-data */}
            <div className="font-mono text-xl font-semibold text-signal-data">
              {incident ? skeptic.toFixed(2) : "—"}
            </div>
          </div>
          <ShieldAlert className="h-5 w-5 text-signal-rejected" />
        </div>
      </div>

      {/* Bidirectional Tug-of-War Bar (Corroborator pushes right, Skeptic pushes left) */}
      <div className="space-y-1.5">
        <div className="relative h-6 overflow-hidden rounded border border-line bg-bg-void">
          {/* Center line at 50% balance mark */}
          <div className="absolute inset-y-0 left-1/2 z-10 w-px bg-line" />

          {/* Skeptic fill pushing from left */}
          <motion.div
            className="absolute inset-y-0 left-0 bg-signal-rejected/30 border-r border-signal-rejected"
            animate={{ width: `${100 - pull}%` }}
            transition={{ type: "spring", stiffness: 120, damping: 14, restDelta: 0.001 }}
          />

          {/* Corroborator fill pushing from right */}
          <motion.div
            className="absolute inset-y-0 right-0 bg-signal-verified/30 border-l border-signal-verified"
            animate={{ width: `${pull}%` }}
            transition={{ type: "spring", stiffness: 120, damping: 14, restDelta: 0.001 }}
          />

          {/* Center dynamic needle */}
          <motion.div
            className="absolute inset-y-0 z-20 w-1 bg-text-primary"
            animate={{ left: `calc(${pull}% - 2px)` }}
            transition={{ type: "spring", stiffness: 120, damping: 14, restDelta: 0.001 }}
          />
        </div>

        {/* Telemetry criteria labels */}
        <div className="flex justify-between font-mono text-label text-text-muted">
          <span>
            Margin:{" "}
            <span className={incident ? "text-signal-data" : "text-text-muted"}>
              {incident ? margin.toFixed(2) : "—"}
            </span>{" "}
            (req &gt; {MARGIN_THRESHOLD})
          </span>
          <span>Fused req &ge; {FUSED_THRESHOLD.toFixed(2)}</span>
        </div>
      </div>

      {/* Telemetry / Reasoning readout */}
      <div className="mt-3 rounded border border-line bg-bg-void p-2.5 font-mono text-label leading-relaxed text-text-muted">
        <span className="text-text-primary">Reasoning: </span>
        {incident?.reasoning ?? "Awaiting incident stream..."}
      </div>
    </div>
  );
}
