import { useState } from "react";
import { AlertOctagon, Brain, Pause, Play, ShieldAlert, Sliders, XCircle } from "lucide-react";
import type { Incident } from "@/lib/aurashield/types";

interface OperatorControlBarProps {
  automationPaused?: boolean;
  onTogglePause?: (paused: boolean) => void;
  governorSensitivity?: number;
  sensitivity?: number;
  onChangeSensitivity?: (val: number) => void;
  onSensitivityChange?: (val: number) => void;
  incident?: Incident | null;
  onOverrideReject?: (
    incidentId: string,
    reason?: string,
    causeTag?: string,
  ) => Promise<void> | void;
  canReject?: boolean;
  busy?: boolean;
  memoryEnabled?: boolean;
  onToggleMemory?: (enabled: boolean) => void;
}

export function OperatorControlBar({
  automationPaused = false,
  onTogglePause,
  governorSensitivity,
  sensitivity: propSensitivity,
  onChangeSensitivity,
  onSensitivityChange,
  incident = null,
  onOverrideReject,
  canReject,
  busy = false,
  memoryEnabled = true,
  onToggleMemory,
}: OperatorControlBarProps) {
  const currentSensitivity = governorSensitivity ?? propSensitivity ?? 0.65;
  const handleSensitivityChange = onChangeSensitivity ?? onSensitivityChange ?? (() => {});
  const handleTogglePause = onTogglePause ? () => onTogglePause(!automationPaused) : () => {};
  const [rejectReason, setRejectReason] = useState("");
  const [causeTag, setCauseTag] = useState<string>("glare");
  const [showRejectModal, setShowRejectModal] = useState(false);

  const canOverrideReject =
    Boolean(incident) && incident?.state !== "REJECTED" && incident?.state !== "CLOSED";

  const handleConfirmReject = () => {
    if (!incident) return;
    onOverrideReject?.(
      incident.id,
      rejectReason.trim() || `Operator manual override: marked as false positive (${causeTag})`,
      causeTag,
    );
    setShowRejectModal(false);
    setRejectReason("");
  };

  return (
    <div className="flex flex-col gap-3 rounded border border-line bg-bg-panel p-4">
      {/* Bar Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2.5">
        <div className="flex items-center gap-2">
          <Sliders className="h-4 w-4 text-signal-data" />
          <span className="font-sans text-label font-semibold text-text-primary">
            Operator Safety Controls
          </span>
          <span className="text-line">/</span>
          <span className="font-sans text-xs text-text-muted">
            Human-in-the-loop override &amp; sensitivity tuning
          </span>
        </div>

        <div className="flex items-center gap-2">
          {onToggleMemory && (
            <button
              onClick={() => onToggleMemory(!memoryEnabled)}
              className={`flex items-center gap-1.5 rounded border px-2.5 py-1 font-mono text-xs font-semibold transition-colors ${
                memoryEnabled
                  ? "border-purple-500/60 bg-purple-500/20 text-purple-300 hover:bg-purple-500/30"
                  : "border-line bg-bg-void text-text-muted hover:border-text-primary hover:text-text-primary"
              }`}
            >
              <Brain className="h-3.5 w-3.5" />
              <span>{memoryEnabled ? "MEMORY: ACTIVE" : "MEMORY: OFF"}</span>
            </button>
          )}

          {automationPaused && (
            <div className="flex items-center gap-2 rounded border border-signal-rejected/60 bg-signal-rejected/15 px-3 py-1 font-mono text-xs font-semibold text-signal-rejected animate-pulse">
              <AlertOctagon className="h-4 w-4" />
              <span>AUTOMATION PAUSED BY OPERATOR</span>
            </div>
          )}
        </div>
      </div>

      {/* Control Grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3 items-center">
        {/* 1. Pause Automation Toggle */}
        <div className="flex items-center justify-between rounded border border-line bg-bg-void p-3">
          <div className="flex items-center gap-2.5">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded ${
                automationPaused
                  ? "bg-signal-rejected/20 text-signal-rejected"
                  : "bg-signal-verified/20 text-signal-verified"
              }`}
            >
              {automationPaused ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            </div>
            <div>
              <div className="font-sans text-label font-medium text-text-primary">
                Automation State
              </div>
              <div className="font-mono text-[11px] text-text-muted">
                {automationPaused ? "Halted before clearance" : "Active auto-pipeline"}
              </div>
            </div>
          </div>

          <button
            onClick={handleTogglePause}
            className={`flex items-center gap-1.5 rounded border px-3 py-1.5 font-sans text-xs font-semibold transition-colors ${
              automationPaused
                ? "border-signal-verified/60 bg-signal-verified/20 text-signal-verified hover:bg-signal-verified/30"
                : "border-signal-rejected/60 bg-signal-rejected/20 text-signal-rejected hover:bg-signal-rejected/30"
            }`}
          >
            {automationPaused ? "RESUME AUTOMATION" : "PAUSE AUTOMATION"}
          </button>
        </div>

        {/* 2. Governor Sensitivity Slider */}
        <div className="flex flex-col gap-1.5 rounded border border-line bg-bg-void p-3">
          <div className="flex items-center justify-between">
            <label
              htmlFor="governor-sensitivity-slider"
              className="font-sans text-label font-medium text-text-primary flex items-center gap-1.5"
            >
              <span>GOVERNOR SENSITIVITY</span>
            </label>
            <div className="font-mono text-sm font-semibold text-signal-data">
              {(currentSensitivity * 100).toFixed(0)}%{" "}
              <span className="text-[11px] text-text-muted">({currentSensitivity.toFixed(2)})</span>
            </div>
          </div>

          <input
            id="governor-sensitivity-slider"
            type="range"
            min="0.50"
            max="0.95"
            step="0.01"
            value={currentSensitivity}
            onChange={(e) => handleSensitivityChange(parseFloat(e.target.value))}
            className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-bg-panel-raised accent-signal-data"
          />

          <div className="flex justify-between font-mono text-[10px] text-text-muted">
            <span>0.50 (Permissive)</span>
            <span>Default: 0.65</span>
            <span>0.95 (Strict)</span>
          </div>
        </div>

        {/* 3. Operator Override: Reject Button */}
        <div className="flex items-center justify-between rounded border border-line bg-bg-void p-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded bg-signal-rejected/10 text-signal-rejected">
              <ShieldAlert className="h-4 w-4" />
            </div>
            <div>
              <div className="font-sans text-label font-medium text-text-primary">
                Operator Override
              </div>
              <div className="font-mono text-[11px] text-text-muted">
                {canOverrideReject
                  ? `Active: ${incident?.id} (${incident?.state})`
                  : "Standby (no active incident)"}
              </div>
            </div>
          </div>

          <button
            disabled={!canOverrideReject || busy}
            onClick={() => setShowRejectModal(true)}
            className="flex items-center gap-1.5 rounded border border-signal-rejected/60 bg-signal-rejected/20 px-3 py-1.5 font-sans text-xs font-semibold text-signal-rejected transition-colors hover:bg-signal-rejected/30 disabled:opacity-40"
          >
            <XCircle className="h-3.5 w-3.5" />
            <span>OVERRIDE: REJECT</span>
          </button>
        </div>
      </div>

      {/* Reject Confirmation Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-md rounded border border-signal-rejected bg-bg-panel p-5 shadow-2xl">
            <div className="flex items-center gap-2 text-signal-rejected">
              <ShieldAlert className="h-5 w-5" />
              <h3 className="font-sans text-panel-header font-semibold">
                Confirm Operator Override: Reject
              </h3>
            </div>
            <p className="mt-2 font-sans text-body text-text-muted">
              You are manually overriding the autonomous safety governor for incident{" "}
              <span className="font-mono font-bold text-text-primary">{incident?.id}</span>. This
              rejection will be permanently recorded in the cryptographic audit ledger.
            </p>

            <div className="mt-4">
              <label className="font-sans text-label text-text-muted">
                Root Cause Category (Retained to Hindsight Memory):
              </label>
              <div className="mt-1.5 flex flex-wrap gap-2">
                {[
                  { id: "glare", label: "Glare / Low Sun" },
                  { id: "shadow", label: "Shadow / Occlusion" },
                  { id: "vibration", label: "Camera Vibration" },
                  { id: "mast_shake", label: "Mast Shake" },
                  { id: "other", label: "Other / Sensor" },
                ].map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setCauseTag(opt.id)}
                    className={`rounded border px-2.5 py-1 font-mono text-xs transition-colors ${
                      causeTag === opt.id
                        ? "border-purple-400 bg-purple-500/25 text-purple-300 font-bold"
                        : "border-line bg-bg-void text-text-muted hover:border-text-primary"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-4">
              <label
                htmlFor="override-reject-reason"
                className="font-sans text-label text-text-muted"
              >
                Override Rationale:
              </label>
              <input
                id="override-reject-reason"
                type="text"
                placeholder="e.g. False alarm: sunlight reflection on camera sensor"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                className="mt-1 w-full rounded border border-line bg-bg-void px-3 py-2 font-sans text-body text-text-primary focus:border-signal-data focus:outline-none"
              />
            </div>

            <div className="mt-5 flex justify-end gap-3">
              <button
                onClick={() => setShowRejectModal(false)}
                className="rounded border border-line px-3 py-1.5 font-sans text-label text-text-muted hover:border-text-primary hover:text-text-primary"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReject}
                className="rounded border border-signal-rejected bg-signal-rejected px-4 py-1.5 font-sans text-label font-semibold text-bg-void hover:opacity-90"
              >
                Confirm Override Reject
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
