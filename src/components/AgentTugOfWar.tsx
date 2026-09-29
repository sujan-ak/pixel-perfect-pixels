import { motion } from "framer-motion";
import { AlertTriangle, ShieldAlert, ShieldCheck } from "lucide-react";
import type { Incident } from "@/lib/aurashield/types";

const FUSED_THRESHOLD = 0.35;
const CONFIDENCE_THRESHOLD = 0.8;

export function AgentTugOfWar({ incident }: { incident: Incident | null }) {
  const corroborator = incident?.corroborator_score ?? 0;
  const skeptic = incident?.skeptic_score ?? 0;
  const fused = incident?.fused_score ?? 0;
  const confidence = incident?.confidence ?? 0.9;

  const preMemoryFused = incident?.memory?.pre_memory_scores?.fused;
  const memoryApplied = Boolean(
    incident?.memory?.adjustment?.applied && preMemoryFused !== undefined,
  );
  const isSuppressed =
    Boolean(incident?.memory?.suppressed_by_memory) ||
    (incident?.memory?.adjustment?.applied &&
      incident.memory.adjustment.dominant === "false_alarm" &&
      incident.state === "REJECTED");

  // Unified -1..+1 scale mapped to 0..100%
  const barPercent = Math.max(0, Math.min(100, ((fused + 1) / 2) * 100));
  const preBarPercent =
    preMemoryFused !== undefined
      ? Math.max(0, Math.min(100, ((preMemoryFused + 1) / 2) * 100))
      : null;
  const markerPercent = ((FUSED_THRESHOLD + 1) / 2) * 100; // 67.5%
  const thresholdMet = fused > FUSED_THRESHOLD && confidence >= CONFIDENCE_THRESHOLD;

  return (
    <div className="flex h-full flex-col justify-between rounded border border-line bg-bg-panel p-4">
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-line pb-2.5">
        <div className="flex items-center gap-2">
          <span className="font-sans text-panel-header text-text-primary">Agent adjudication</span>
          <span className="font-sans text-label text-text-muted">/ dual-model fusion</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isSuppressed && (
            <span className="flex items-center gap-1 rounded border border-purple-500/60 bg-purple-500/20 px-2 py-0.5 font-mono text-[10px] font-semibold text-purple-300">
              <ShieldAlert className="h-3 w-3 text-purple-400" />
              <span>
                Suppressed by memory (
                {incident?.memory?.adjustment?.dominant_count ??
                  incident?.memory?.precedents?.length ??
                  3}{" "}
                precedents)
              </span>
            </span>
          )}
          {incident?.degraded && (
            <span className="flex items-center gap-1 rounded border border-signal-pending/60 bg-signal-pending/15 px-2 py-0.5 font-mono text-[10px] font-semibold text-signal-pending animate-pulse">
              <AlertTriangle className="h-3 w-3" />
              <span>AGENT DEGRADED · HEURISTIC FALLBACK</span>
            </span>
          )}
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
          {memoryApplied && preMemoryFused !== undefined && (
            <div className="flex items-center justify-center gap-1 font-mono text-[11px] text-text-muted">
              <span className="text-amber-400 line-through">
                {preMemoryFused > 0 ? `+${preMemoryFused.toFixed(2)}` : preMemoryFused.toFixed(2)}
              </span>
              <span>&rarr;</span>
              <span className="text-purple-400 font-bold">
                Δ {(fused - preMemoryFused).toFixed(2)}
              </span>
            </div>
          )}
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

      {/* Bidirectional Tug-of-War Bar on unified -1..+1 scale */}
      <div className="space-y-1.5">
        <div className="relative h-6 overflow-hidden rounded border border-line bg-bg-void">
          {/* Center line at 50% balance mark (fused = 0) */}
          <div className="absolute inset-y-0 left-1/2 z-10 w-px bg-line" />

          {/* Dashed threshold marker at ((0.35 + 1) / 2) * 100 = 67.5% */}
          <div
            className="absolute inset-y-0 z-10 w-0 border-r-2 border-dashed border-signal-verified/90"
            style={{ left: `${markerPercent}%` }}
            title="Verification Threshold (fused > 0.35)"
          />

          {/* Fill on unified scale: pushes from center 50% toward barPercent */}
          <motion.div
            className={`absolute inset-y-0 ${
              fused >= 0
                ? "bg-signal-verified/30 border-r border-signal-verified"
                : "bg-signal-rejected/30 border-l border-signal-rejected"
            }`}
            animate={{
              left: fused >= 0 ? "50%" : `${barPercent}%`,
              width: `${Math.abs(barPercent - 50)}%`,
            }}
            transition={{ type: "spring", stiffness: 120, damping: 14, restDelta: 0.001 }}
          />

          {/* Center dynamic needle */}
          <motion.div
            className="absolute inset-y-0 z-20 w-1 bg-text-primary"
            animate={{ left: `calc(${barPercent}% - 2px)` }}
            transition={{ type: "spring", stiffness: 120, damping: 14, restDelta: 0.001 }}
          />

          {/* Pre-memory ghost needle (if memory adjusted) */}
          {memoryApplied && preBarPercent !== null && (
            <div
              className="absolute inset-y-0 z-20 w-0 border-r-2 border-dashed border-amber-400"
              style={{ left: `${preBarPercent}%` }}
              title={`Pre-memory raw score: ${preMemoryFused !== undefined && preMemoryFused > 0 ? `+${preMemoryFused.toFixed(2)}` : preMemoryFused?.toFixed(2)}`}
            />
          )}
        </div>

        {/* Telemetry criteria labels */}
        <div className="flex justify-between font-mono text-label text-text-muted">
          <span>
            Confidence:{" "}
            <span className={incident ? "text-signal-data" : "text-text-muted"}>
              {incident ? confidence.toFixed(2) : "—"}
            </span>{" "}
            (req &ge; {CONFIDENCE_THRESHOLD.toFixed(2)})
          </span>
          <span>Fused req &gt; {FUSED_THRESHOLD.toFixed(2)} (gate: 67.5%)</span>
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
