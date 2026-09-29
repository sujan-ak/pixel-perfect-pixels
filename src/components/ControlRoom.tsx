import { useState, useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  CarFront,
  CheckCircle,
  Clock,
  MessageSquare,
  Play,
  Power,
  RotateCcw,
  Shield,
  Sun,
  X,
} from "lucide-react";
import { AgentTugOfWar } from "./AgentTugOfWar";
import { AuditLedger } from "./AuditLedger";
import { IncidentHistory } from "./IncidentHistory";
import { MemoryPanel } from "./MemoryPanel";
import { OperatorControlBar } from "./OperatorControlBar";
import { LiveMap } from "./LiveMap";
import { ReasoningTerminal } from "./ReasoningTerminal";
import { StateTracker } from "./StateTracker";
import { VideoFeed } from "./VideoFeed";
import { useAuraShield } from "@/lib/aurashield/useAuraShield";

export function ControlRoom() {
  const {
    mode,
    setMode,
    link,
    incident,
    audit,
    sms,
    setSms,
    chain,
    busy,
    triggerScenario,
    approveDispatch,
    verifyChain,
    tamperDemo,
    restoreDemo,
    reset,
    reasoningLogs,
    isStreaming,
    automationPaused,
    setAutomationPaused,
    governorSensitivity,
    setGovernorSensitivity,
    overrideReject,
    clearReasoningLogs,
    memoryEnabled,
    setMemoryEnabled,
    memoryStatus,
    refreshMemoryStatus,
    precedents,
    insights,
    refreshInsights,
    learningCurve,
    refreshLearningCurve,
    memoryTimeline,
    refreshTimeline,
  } = useAuraShield();

  const [utcTime, setUtcTime] = useState("");
  const [runningBoth, setRunningBoth] = useState(false);
  const incidentRef = useRef(incident);
  const awaitingClearance = incident?.state === "RESPONSE_PROPOSED";

  useEffect(() => {
    incidentRef.current = incident;
  }, [incident]);

  const handleRunBoth = async () => {
    if (busy || runningBoth) return;
    setRunningBoth(true);
    try {
      await triggerScenario("crash_zone04");

      // Poll until incident reaches RESPONSE_PROPOSED, REJECTED, or CLOSED
      const start = Date.now();
      await new Promise((r) => setTimeout(r, 800));

      while (Date.now() - start < 35000) {
        const curr = incidentRef.current;
        if (
          curr &&
          (curr.state === "RESPONSE_PROPOSED" ||
            curr.state === "REJECTED" ||
            curr.state === "CLOSED")
        ) {
          break;
        }
        await new Promise((r) => setTimeout(r, 500));
      }

      // Wait 3 seconds per specification
      await new Promise((r) => setTimeout(r, 3000));

      // Trigger false alarm scenario
      await triggerScenario("false_alarm");
    } finally {
      setRunningBoth(false);
    }
  };

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setUtcTime(now.toISOString().slice(11, 19) + " UTC");
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-bg-void text-text-primary flex flex-col font-sans">
      {/* 1. Top Bar: 56px fixed height */}
      <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b border-line bg-bg-panel px-5">
        {/* Brand & Context */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-signal-verified" />
            <span className="font-sans text-body font-semibold tracking-wide text-text-primary">
              AuraShield
            </span>
          </div>
          <span className="text-line">/</span>
          <span className="font-sans text-label text-text-muted">
            Safety-governed incident control room
          </span>
        </div>

        {/* Status & Live Telemetry Clock */}
        <div className="flex items-center gap-3">
          {/* Pulsing Green Status LED: SYSTEM ACTIVE */}
          <div className="flex items-center gap-2 rounded border border-signal-verified/40 bg-signal-verified/10 px-2.5 py-1 font-mono text-label font-medium text-signal-verified">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-signal-verified opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-signal-verified" />
            </span>
            <span>SYSTEM ACTIVE</span>
          </div>

          {/* Live UTC Clock */}
          <div className="hidden sm:flex items-center gap-1.5 rounded border border-line bg-bg-void px-2.5 py-1 font-mono text-label text-text-muted">
            <Clock className="h-3.5 w-3.5 text-text-muted" />
            <span>{utcTime}</span>
          </div>

          {/* Connection Status Badge */}
          <div
            className={`flex items-center gap-1.5 rounded border px-2.5 py-1 font-sans text-label font-medium ${
              mode === "live"
                ? link === "online"
                  ? "border-signal-verified text-signal-verified bg-signal-verified/10"
                  : link === "connecting"
                    ? "border-signal-pending text-signal-pending bg-signal-pending/10"
                    : "border-signal-rejected text-signal-rejected bg-signal-rejected/10"
                : "border-signal-pending text-signal-pending bg-signal-pending/10"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                mode === "live"
                  ? link === "online"
                    ? "bg-signal-verified animate-pulse"
                    : link === "connecting"
                      ? "bg-signal-pending animate-pulse"
                      : "bg-signal-rejected"
                  : "bg-signal-pending"
              }`}
            />
            <span>
              {mode === "live"
                ? link === "online"
                  ? "Live backend · Online"
                  : link === "connecting"
                    ? "Live backend · Connecting..."
                    : "Live feed disconnected — retrying in 3s..."
                : "Mock data mode"}
            </span>
          </div>

          {/* Mode Switch Toggle Button */}
          <button
            onClick={() => {
              reset();
              setMode(mode === "mock" ? "live" : "mock");
            }}
            className="flex items-center gap-1.5 rounded border border-line bg-bg-panel-raised px-2.5 py-1 font-sans text-label text-text-primary transition-colors hover:border-text-primary focus-visible:ring-1 focus-visible:ring-signal-data"
          >
            <Power className="h-3.5 w-3.5 text-text-muted" />
            <span>Switch to {mode === "mock" ? "live" : "mock"}</span>
          </button>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="mx-auto flex w-full max-w-[1520px] flex-1 flex-col gap-4 p-5">
        {/* Scenario Controls Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded border border-line bg-bg-panel px-4 py-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-sans text-label text-text-muted mr-1">Trigger scenarios:</span>
            <button
              disabled={busy || runningBoth}
              onClick={() => triggerScenario("crash_zone04")}
              className="flex items-center gap-2 rounded border border-signal-verified/40 bg-signal-verified/10 px-3 py-1.5 font-sans text-label font-medium text-signal-verified transition-colors hover:bg-signal-verified/20 disabled:opacity-40 focus-visible:ring-1 focus-visible:ring-signal-data"
            >
              <CarFront className="h-4 w-4" />
              <span>Trigger crash scenario</span>
            </button>

            <button
              disabled={busy || runningBoth}
              onClick={() => triggerScenario("false_alarm")}
              className="flex items-center gap-2 rounded border border-signal-pending/40 bg-signal-pending/10 px-3 py-1.5 font-sans text-label font-medium text-signal-pending transition-colors hover:bg-signal-pending/20 disabled:opacity-40 focus-visible:ring-1 focus-visible:ring-signal-data"
            >
              <AlertTriangle className="h-4 w-4" />
              <span>Trigger false alarm scenario</span>
            </button>

            <button
              disabled={busy || runningBoth}
              onClick={() => triggerScenario("glare_ambiguous")}
              className="flex items-center gap-2 rounded border border-purple-500/40 bg-purple-500/10 px-3 py-1.5 font-sans text-label font-medium text-purple-300 transition-colors hover:bg-purple-500/20 disabled:opacity-40 focus-visible:ring-1 focus-visible:ring-signal-data"
            >
              <Sun className="h-4 w-4 text-purple-400" />
              <span>Trigger ambiguous glare scenario</span>
            </button>

            <button
              disabled={busy || runningBoth}
              onClick={handleRunBoth}
              className={`flex items-center gap-2 rounded border px-3 py-1.5 font-sans text-label font-medium transition-colors focus-visible:ring-1 focus-visible:ring-signal-data disabled:opacity-40 ${
                runningBoth
                  ? "border-signal-data bg-signal-data/20 text-signal-data animate-pulse"
                  : "border-signal-data/50 bg-signal-data/10 text-signal-data hover:bg-signal-data/20"
              }`}
            >
              <Play className="h-4 w-4" />
              <span>{runningBoth ? "Running batch sequence..." : "RUN BOTH SCENARIOS"}</span>
            </button>
          </div>

          <button
            onClick={reset}
            disabled={runningBoth}
            className="flex items-center gap-1.5 rounded border border-line bg-bg-panel-raised px-3 py-1.5 font-sans text-label text-text-muted transition-colors hover:border-text-primary hover:text-text-primary disabled:opacity-40 focus-visible:ring-1 focus-visible:ring-signal-data"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Reset console</span>
          </button>
        </div>

        {/* 2. Three-Zone Control Room Center Layout */}
        <div className="grid gap-4 lg:grid-cols-12 items-stretch">
          {/* Left Zone: Video Feed / Incident Primary View (~60% width = 7 of 12 cols) */}
          <div className="lg:col-span-7 flex flex-col justify-center">
            <VideoFeed incident={incident} />
          </div>

          {/* Right Rail: Agent Adjudication & State Machine (5 of 12 cols) */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            <div className="flex-1">
              <AgentTugOfWar incident={incident} />
            </div>
            <div>
              <StateTracker state={incident?.state ?? null} incident={incident} />
            </div>
          </div>
        </div>

        {/* Operator Controls: Automation pause, Reject override, Sensitivity slider */}
        <OperatorControlBar
          automationPaused={automationPaused}
          onTogglePause={() => setAutomationPaused(!automationPaused)}
          incident={incident}
          onOverrideReject={overrideReject}
          canReject={Boolean(
            incident && incident.state !== "REJECTED" && incident.state !== "CLOSED",
          )}
          sensitivity={governorSensitivity}
          onSensitivityChange={setGovernorSensitivity}
          busy={busy}
          memoryEnabled={memoryEnabled}
          onToggleMemory={setMemoryEnabled}
        />

        {/* Live Adversarial Streaming Reasoning Terminal */}
        <ReasoningTerminal
          logs={reasoningLogs}
          isStreaming={isStreaming}
          onClear={clearReasoningLogs}
        />

        {/* Awaiting Operator Clearance Decision Banner */}
        <AnimatePresence>
          {awaitingClearance && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.2 }}
              className="flex flex-wrap items-center justify-between gap-4 rounded border border-signal-verified bg-signal-verified/10 p-4"
            >
              <div>
                <div className="flex items-center gap-2 font-sans text-panel-header text-signal-verified">
                  <CheckCircle className="h-5 w-5" />
                  <span>Awaiting operator clearance</span>
                </div>
                <p className="mt-1 font-sans text-body text-text-primary">
                  <span className="font-semibold text-signal-verified">{incident?.zone}</span>{" "}
                  &middot; Dual-agent threshold met. Automated dispatch requires an authenticated
                  operator decision.
                </p>
              </div>

              <button
                onClick={approveDispatch}
                disabled={busy || automationPaused}
                className="flex items-center gap-2 rounded bg-signal-verified px-5 py-2 font-sans text-body font-semibold text-bg-void transition-opacity hover:opacity-90 disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-signal-data"
              >
                <span>{automationPaused ? "Automation paused" : "Approve dispatch"}</span>
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Geospatial Control: Hyderabad Leaflet Map & Green Corridor Actuation */}
        <LiveMap
          incident={incident}
          isApproved={Boolean(
            incident &&
            ["OPERATOR_APPROVED", "COORDINATION_IN_PROGRESS", "ACKNOWLEDGED", "CLOSED"].includes(
              incident.state,
            ),
          )}
          onSignalActuated={() => {
            verifyChain();
          }}
        />

        {/* Hindsight Persistent Operational Memory & Learning Curve */}
        <div>
          <MemoryPanel
            memoryEnabled={memoryEnabled}
            onToggleMemory={setMemoryEnabled}
            memoryStatus={memoryStatus}
            precedents={precedents}
            insights={insights}
            onRefreshInsights={refreshInsights}
            learningCurve={learningCurve}
            onRefreshLearningCurve={refreshLearningCurve}
            timeline={memoryTimeline}
            onRefreshTimeline={refreshTimeline}
            currentIncident={incident}
            busy={busy}
          />
        </div>

        {/* 3. Bottom Zone: Immutable Monospace Audit Ledger */}
        <div>
          <AuditLedger
            entries={audit}
            chain={chain}
            onVerify={verifyChain}
            onTamper={tamperDemo}
            onRestore={restoreDemo}
          />
        </div>

        {/* 4. Incident History Panel (Compact records from GET /incidents/history) */}
        <div>
          <IncidentHistory currentIncidentState={incident?.state ?? null} />
        </div>
      </main>

      {/* SMS Dispatched Modal */}
      <AnimatePresence>
        {sms && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-bg-void/80 backdrop-blur-sm p-4"
          >
            <motion.div
              initial={{ scale: 0.98 }}
              animate={{ scale: 1 }}
              className="w-full max-w-lg rounded border border-signal-verified bg-bg-panel p-5"
            >
              <div className="flex items-center justify-between border-b border-line pb-3">
                <span className="flex items-center gap-2 font-sans text-panel-header text-signal-verified">
                  <MessageSquare className="h-5 w-5" />
                  <span>SMS dispatch notification transmitted</span>
                </span>
                <button
                  onClick={() => setSms(null)}
                  className="rounded p-1 text-text-muted hover:text-text-primary transition-colors focus-visible:ring-1 focus-visible:ring-signal-data"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="mt-4 space-y-2 rounded border border-line bg-bg-void p-3 font-mono text-label">
                <div className="flex gap-2">
                  <span className="text-text-muted w-14">To:</span>
                  <span className="text-text-primary">{sms.to}</span>
                </div>
                <div className="flex gap-2">
                  <span className="text-text-muted w-14">From:</span>
                  <span className="text-text-primary">{sms.from}</span>
                </div>
                <div className="flex gap-2">
                  <span className="text-text-muted w-14">Sent:</span>
                  <span className="text-text-primary">{sms.timestamp}</span>
                </div>
                <div className="border-t border-line/60 pt-2 text-text-primary leading-relaxed">
                  {sms.body}
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
