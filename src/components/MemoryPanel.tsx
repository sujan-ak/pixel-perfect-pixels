import { useState } from "react";
import {
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Database,
  History,
  Info,
  RefreshCw,
  Shield,
  ShieldAlert,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import type {
  Incident,
  LearningCurvePoint,
  MemoryEvent,
  MemoryStatus,
  Precedent,
} from "@/lib/aurashield/types";

interface MemoryPanelProps {
  memoryEnabled: boolean;
  onToggleMemory: (enabled: boolean) => Promise<void> | void;
  memoryStatus: MemoryStatus | null;
  precedents: Precedent[];
  insights: string | null;
  onRefreshInsights: () => Promise<void> | void;
  learningCurve: LearningCurvePoint[];
  onRefreshLearningCurve: () => Promise<void> | void;
  timeline: MemoryEvent[];
  onRefreshTimeline: () => Promise<void> | void;
  currentIncident?: Incident | null;
  busy?: boolean;
}

export function MemoryPanel({
  memoryEnabled,
  onToggleMemory,
  memoryStatus,
  precedents,
  insights,
  onRefreshInsights,
  learningCurve,
  onRefreshLearningCurve,
  timeline,
  onRefreshTimeline,
  currentIncident,
  busy = false,
}: MemoryPanelProps) {
  const [showAllPrecedents, setShowAllPrecedents] = useState(false);
  const [activeTab, setActiveTab] = useState<"learning" | "precedents" | "insights" | "timeline">(
    "learning",
  );
  const [isRefreshing, setIsRefreshing] = useState(false);

  const activePrecedents = currentIncident?.memory?.precedents?.length
    ? currentIncident.memory.precedents
    : precedents;

  const adjustment = currentIncident?.memory?.adjustment;
  const isSuppressed =
    Boolean(currentIncident?.memory?.suppressed_by_memory) ||
    (adjustment?.applied &&
      adjustment.dominant === "false_alarm" &&
      currentIncident?.state === "REJECTED");

  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    try {
      await Promise.allSettled([
        onRefreshInsights(),
        onRefreshLearningCurve(),
        onRefreshTimeline(),
      ]);
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="flex flex-col rounded border border-line bg-bg-panel overflow-hidden">
      {/* 1. Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-bg-panel-raised px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded border border-purple-500/40 bg-purple-500/15 text-purple-400">
            <Brain className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold tracking-wide text-text-primary">
                HINDSIGHT MEMORY
              </span>
              <span className="text-line">/</span>
              <span className="font-sans text-xs text-text-muted">
                Persistent Operational Learning
              </span>
            </div>
            <div className="flex items-center gap-2 font-mono text-[11px] text-text-muted">
              <span>Bank: {memoryStatus?.bank_id ?? "aurashield-operations"}</span>
              <span>&middot;</span>
              <span>{memoryStatus?.events_in_ledger ?? timeline.length} events retained</span>
            </div>
          </div>
        </div>

        {/* Status indicator & Quick Toggle */}
        <div className="flex items-center gap-3">
          {/* Status badge */}
          <div
            className={`flex items-center gap-1.5 rounded border px-2.5 py-1 font-mono text-xs ${
              !memoryEnabled
                ? "border-line bg-bg-void text-text-muted"
                : memoryStatus?.hindsight_reachable
                  ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-400"
                  : "border-amber-500/50 bg-amber-500/10 text-amber-400"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                !memoryEnabled
                  ? "bg-text-muted"
                  : memoryStatus?.hindsight_reachable
                    ? "bg-emerald-400 animate-pulse"
                    : "bg-amber-400 animate-pulse"
              }`}
            />
            <span className="font-semibold">
              {!memoryEnabled
                ? "MEMORY DISABLED"
                : memoryStatus?.hindsight_reachable
                  ? "HINDSIGHT CLOUD"
                  : "LOCAL FALLBACK"}
            </span>
          </div>

          {/* Quick Toggle Button */}
          <button
            disabled={busy}
            onClick={() => onToggleMemory(!memoryEnabled)}
            className={`flex items-center gap-1.5 rounded border px-3 py-1 font-mono text-xs font-bold transition-colors ${
              memoryEnabled
                ? "border-purple-500/60 bg-purple-500/20 text-purple-300 hover:bg-purple-500/30"
                : "border-line bg-bg-void text-text-muted hover:border-text-primary hover:text-text-primary"
            }`}
          >
            <span>{memoryEnabled ? "MEMORY: ON" : "MEMORY: OFF"}</span>
          </button>

          {/* Global Refresh Button */}
          <button
            onClick={handleRefreshAll}
            disabled={isRefreshing || busy}
            title="Refresh memory insights, learning curve, and timeline"
            className="flex h-7 w-7 items-center justify-center rounded border border-line bg-bg-panel text-text-muted transition-colors hover:border-text-primary hover:text-text-primary disabled:opacity-40"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* 2. Memory Impact Strip (Shown whenever active incident has memory adjustment) */}
      {currentIncident?.memory && (
        <div className="border-b border-line bg-purple-950/20 p-4">
          {/* Suppression alert banner if suppressed by memory */}
          {isSuppressed && (
            <div className="mb-3 flex items-center justify-between rounded border border-purple-500/60 bg-purple-900/30 px-3.5 py-2">
              <div className="flex items-center gap-2 text-purple-300">
                <ShieldAlert className="h-4 w-4 shrink-0 text-purple-400" />
                <span className="font-mono text-xs font-bold uppercase tracking-wider">
                  Suppressed by memory ({adjustment?.dominant_count ?? activePrecedents.length}{" "}
                  precedents)
                </span>
                <span className="text-text-muted">&middot;</span>
                <span className="font-sans text-xs text-purple-200">
                  Recurring false alarms confirmed in {currentIncident.zone}. Autonomous veto
                  applied.
                </span>
              </div>
              <span className="rounded bg-purple-500/20 px-2 py-0.5 font-mono text-[10px] font-semibold text-purple-300">
                ASYMMETRIC SAFETY RULE
              </span>
            </div>
          )}

          {/* Scores Comparison Grid */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {/* Corroborator Impact */}
            <div className="rounded border border-line bg-bg-void p-2.5">
              <div className="flex items-center justify-between">
                <span className="font-sans text-xs text-text-muted">Corroborator</span>
                <span className="font-mono text-[11px] text-text-muted">
                  Δ{" "}
                  {adjustment
                    ? adjustment.corr_delta >= 0
                      ? `+${adjustment.corr_delta.toFixed(2)}`
                      : adjustment.corr_delta.toFixed(2)
                    : "0.00"}
                </span>
              </div>
              <div className="mt-1 flex items-baseline gap-2 font-mono">
                <span className="text-xs text-text-muted line-through">
                  {currentIncident.memory.pre_memory_scores.corr.toFixed(2)}
                </span>
                <span className="text-sm font-bold text-signal-verified">
                  {currentIncident.memory.post_memory_scores.corr.toFixed(2)}
                </span>
              </div>
            </div>

            {/* Skeptic Impact */}
            <div className="rounded border border-line bg-bg-void p-2.5">
              <div className="flex items-center justify-between">
                <span className="font-sans text-xs text-text-muted">Skeptic (Elevated)</span>
                <span className="font-mono text-[11px] text-purple-400">
                  Δ{" "}
                  {adjustment
                    ? adjustment.skep_delta >= 0
                      ? `+${adjustment.skep_delta.toFixed(2)}`
                      : adjustment.skep_delta.toFixed(2)
                    : "0.00"}
                </span>
              </div>
              <div className="mt-1 flex items-baseline gap-2 font-mono">
                <span className="text-xs text-text-muted line-through">
                  {currentIncident.memory.pre_memory_scores.skep.toFixed(2)}
                </span>
                <span className="text-sm font-bold text-rose-400">
                  {currentIncident.memory.post_memory_scores.skep.toFixed(2)}
                </span>
              </div>
            </div>

            {/* Fused Score Delta */}
            <div className="rounded border border-line bg-bg-void p-2.5">
              <div className="flex items-center justify-between">
                <span className="font-sans text-xs text-text-muted">Fused Verdict Delta</span>
                <span
                  className={`font-mono text-[11px] font-bold ${
                    adjustment && adjustment.delta < 0 ? "text-purple-400" : "text-signal-data"
                  }`}
                >
                  Δ{" "}
                  {adjustment
                    ? adjustment.delta >= 0
                      ? `+${adjustment.delta.toFixed(2)}`
                      : adjustment.delta.toFixed(2)
                    : "0.00"}
                </span>
              </div>
              <div className="mt-1 flex items-baseline gap-2 font-mono">
                <span className="text-xs text-text-muted line-through">
                  {currentIncident.memory.pre_memory_scores.fused >= 0
                    ? `+${currentIncident.memory.pre_memory_scores.fused.toFixed(2)}`
                    : currentIncident.memory.pre_memory_scores.fused.toFixed(2)}
                </span>
                <span
                  className={`text-sm font-bold ${
                    currentIncident.memory.post_memory_scores.fused >= 0.35
                      ? "text-signal-verified"
                      : "text-signal-rejected"
                  }`}
                >
                  {currentIncident.memory.post_memory_scores.fused >= 0
                    ? `+${currentIncident.memory.post_memory_scores.fused.toFixed(2)}`
                    : currentIncident.memory.post_memory_scores.fused.toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 3. Navigation Tabs */}
      <div className="flex border-b border-line bg-bg-panel px-4">
        <button
          onClick={() => setActiveTab("learning")}
          className={`flex items-center gap-1.5 border-b-2 px-3 py-2 font-sans text-xs font-semibold transition-colors ${
            activeTab === "learning"
              ? "border-purple-400 text-purple-400"
              : "border-transparent text-text-muted hover:text-text-primary"
          }`}
        >
          <TrendingUp className="h-3.5 w-3.5" />
          <span>Learning Curve</span>
          <span className="rounded bg-bg-void px-1.5 py-0.2 font-mono text-[10px]">
            {learningCurve.length} runs
          </span>
        </button>

        <button
          onClick={() => setActiveTab("precedents")}
          className={`flex items-center gap-1.5 border-b-2 px-3 py-2 font-sans text-xs font-semibold transition-colors ${
            activeTab === "precedents"
              ? "border-purple-400 text-purple-400"
              : "border-transparent text-text-muted hover:text-text-primary"
          }`}
        >
          <Database className="h-3.5 w-3.5" />
          <span>Recalled Precedents</span>
          <span className="rounded bg-bg-void px-1.5 py-0.2 font-mono text-[10px]">
            {activePrecedents.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("insights")}
          className={`flex items-center gap-1.5 border-b-2 px-3 py-2 font-sans text-xs font-semibold transition-colors ${
            activeTab === "insights"
              ? "border-purple-400 text-purple-400"
              : "border-transparent text-text-muted hover:text-text-primary"
          }`}
        >
          <Sparkles className="h-3.5 w-3.5" />
          <span>Learned Insights</span>
        </button>

        <button
          onClick={() => setActiveTab("timeline")}
          className={`flex items-center gap-1.5 border-b-2 px-3 py-2 font-sans text-xs font-semibold transition-colors ${
            activeTab === "timeline"
              ? "border-purple-400 text-purple-400"
              : "border-transparent text-text-muted hover:text-text-primary"
          }`}
        >
          <History className="h-3.5 w-3.5" />
          <span>Memory Timeline</span>
          <span className="rounded bg-bg-void px-1.5 py-0.2 font-mono text-[10px]">
            {timeline.length}
          </span>
        </button>
      </div>

      {/* 4. Tab Content Area */}
      <div className="p-4">
        {/* TAB 1: LEARNING CURVE CHART */}
        {activeTab === "learning" && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-sans text-xs font-bold uppercase tracking-wider text-text-primary">
                  Operational Learning Progression
                </h4>
                <p className="font-sans text-[11px] text-text-muted">
                  Comparison of raw dual-model score vs memory-adjusted score over successive
                  operational runs.
                </p>
              </div>
              <div className="flex items-center gap-4 font-mono text-xs">
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-4 rounded-sm border border-amber-400 bg-amber-400/30" />
                  <span className="text-text-muted">Pre-Memory Fused</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-4 rounded-sm border border-purple-400 bg-purple-400" />
                  <span className="text-purple-300 font-bold">Post-Memory Fused</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-0 w-3 border-t-2 border-dashed border-emerald-400" />
                  <span className="text-text-muted">Threshold (+0.35)</span>
                </div>
              </div>
            </div>

            {learningCurve.length === 0 ? (
              <div className="flex h-44 items-center justify-center rounded border border-line bg-bg-void text-center text-text-muted">
                <div className="flex flex-col items-center gap-1">
                  <TrendingUp className="h-6 w-6 text-text-muted/60" />
                  <span className="text-xs">No operational learning history available yet.</span>
                  <span className="text-[10px]">
                    Trigger scenarios or operator overrides to build the learning trajectory.
                  </span>
                </div>
              </div>
            ) : (
              <div className="h-56 w-full rounded border border-line bg-bg-void p-2">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={learningCurve}
                    margin={{ top: 10, right: 20, left: -20, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2430" />
                    <XAxis
                      dataKey="run"
                      tick={{ fill: "#6b7280", fontSize: 10, fontFamily: "monospace" }}
                      tickFormatter={(val) => `Run ${val}`}
                    />
                    <YAxis
                      domain={[-1, 1]}
                      tick={{ fill: "#6b7280", fontSize: 10, fontFamily: "monospace" }}
                      ticks={[-1.0, -0.5, 0.0, 0.35, 0.7, 1.0]}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload || !payload.length) return null;
                        const data = payload[0].payload as LearningCurvePoint;
                        return (
                          <div className="rounded border border-line bg-[#07090e] p-2.5 font-mono text-xs shadow-xl">
                            <div className="font-bold text-text-primary">
                              Run #{data.run} &middot; {data.scenario}
                            </div>
                            <div className="mt-1 space-y-0.5 text-[11px]">
                              <div className="text-amber-400">
                                Pre-memory:{" "}
                                {data.pre_memory_fused >= 0
                                  ? `+${data.pre_memory_fused.toFixed(2)}`
                                  : data.pre_memory_fused.toFixed(2)}
                              </div>
                              <div className="text-purple-400 font-semibold">
                                Post-memory:{" "}
                                {data.post_memory_fused >= 0
                                  ? `+${data.post_memory_fused.toFixed(2)}`
                                  : data.post_memory_fused.toFixed(2)}
                              </div>
                              <div className="text-text-muted">
                                Precedents in memory: {data.precedents}
                              </div>
                              <div className="text-text-muted">
                                Verdict:{" "}
                                <span
                                  className={
                                    data.verdict === "VERIFIED"
                                      ? "text-emerald-400 font-bold"
                                      : "text-rose-400 font-bold"
                                  }
                                >
                                  {data.verdict}
                                </span>
                              </div>
                            </div>
                          </div>
                        );
                      }}
                    />
                    {/* Verification Threshold Line */}
                    <ReferenceLine
                      y={0.35}
                      stroke="#10b981"
                      strokeDasharray="4 4"
                      strokeWidth={1.5}
                    />
                    {/* Pre-Memory Line */}
                    <Line
                      type="monotone"
                      dataKey="pre_memory_fused"
                      stroke="#f59e0b"
                      strokeWidth={2}
                      strokeDasharray="4 4"
                      dot={{ r: 3, fill: "#f59e0b" }}
                      isAnimationActive={false}
                    />
                    {/* Post-Memory Line */}
                    <Line
                      type="monotone"
                      dataKey="post_memory_fused"
                      stroke="#c084fc"
                      strokeWidth={2.5}
                      dot={{ r: 4, fill: "#c084fc" }}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: RECALLED PRECEDENTS */}
        {activeTab === "precedents" && (
          <div className="flex flex-col gap-2.5">
            <div className="flex items-center justify-between">
              <span className="font-sans text-xs text-text-muted">
                Matched operational records retrieved for current context
              </span>
              {activePrecedents.length > 3 && (
                <button
                  onClick={() => setShowAllPrecedents(!showAllPrecedents)}
                  className="flex items-center gap-1 font-mono text-xs text-purple-400 hover:underline"
                >
                  <span>
                    {showAllPrecedents ? "Show top 3" : `Show all (${activePrecedents.length})`}
                  </span>
                  {showAllPrecedents ? (
                    <ChevronUp className="h-3 w-3" />
                  ) : (
                    <ChevronDown className="h-3 w-3" />
                  )}
                </button>
              )}
            </div>

            {activePrecedents.length === 0 ? (
              <div className="rounded border border-line bg-bg-void p-6 text-center font-sans text-xs text-text-muted">
                No precedent records recalled for this incident yet.
              </div>
            ) : (
              <div className="space-y-2">
                {(showAllPrecedents ? activePrecedents : activePrecedents.slice(0, 3)).map(
                  (item, idx) => (
                    <div
                      key={idx}
                      className="flex flex-col gap-1.5 rounded border border-line bg-bg-void p-3 transition-colors hover:border-purple-500/40"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span
                            className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-bold ${
                              item.source === "hindsight"
                                ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
                                : "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                            }`}
                          >
                            {item.source === "hindsight" ? "HINDSIGHT" : "LOCAL-LEDGER"}
                          </span>
                          {item.relevance !== undefined && (
                            <span className="font-mono text-[11px] font-semibold text-emerald-400">
                              {(item.relevance * 100).toFixed(0)}% Match
                            </span>
                          )}
                          {item.zone && (
                            <span className="font-mono text-[11px] text-text-muted">
                              {item.zone}
                            </span>
                          )}
                        </div>

                        {item.ts && (
                          <span className="font-mono text-[10px] text-text-muted">
                            {new Date(item.ts).toLocaleTimeString()}
                          </span>
                        )}
                      </div>

                      <p className="font-sans text-xs leading-relaxed text-text-primary/90">
                        {item.text}
                      </p>

                      {item.cause_tags && item.cause_tags.length > 0 && (
                        <div className="flex items-center gap-1.5 pt-1">
                          {item.cause_tags.map((tag) => (
                            <span
                              key={tag}
                              className="rounded bg-bg-panel px-1.5 py-0.5 font-mono text-[10px] text-purple-400 border border-line"
                            >
                              #{tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ),
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: LEARNED INSIGHTS */}
        {activeTab === "insights" && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-sans text-xs font-bold uppercase tracking-wider text-text-primary">
                  Synthesized Operational Insights
                </h4>
                <p className="font-sans text-[11px] text-text-muted">
                  Hindsight Continuous Reflection across false alarm causes, recurring camera
                  artifacts, and peak-hour hospital routing.
                </p>
              </div>

              <button
                onClick={onRefreshInsights}
                disabled={busy}
                className="flex items-center gap-1 rounded border border-line bg-bg-void px-2 py-1 font-sans text-xs text-text-muted hover:border-text-primary hover:text-text-primary"
              >
                <RefreshCw className="h-3 w-3" />
                <span>Re-synthesize</span>
              </button>
            </div>

            <div className="rounded border border-purple-500/30 bg-purple-950/20 p-4 font-sans text-xs leading-relaxed text-text-primary">
              {insights ? (
                <div className="whitespace-pre-wrap">{insights}</div>
              ) : (
                <div className="text-text-muted">
                  No synthesized insights recorded yet. Click Re-synthesize to trigger Hindsight
                  reflection.
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 4: MEMORY TIMELINE */}
        {activeTab === "timeline" && (
          <div className="flex flex-col gap-2.5">
            <div className="flex items-center justify-between">
              <span className="font-sans text-xs text-text-muted">
                Audit log of recent observations and operator decisions retained in memory
              </span>
              <button
                onClick={onRefreshTimeline}
                className="font-mono text-xs text-text-muted hover:text-text-primary"
              >
                Refresh
              </button>
            </div>

            {timeline.length === 0 ? (
              <div className="rounded border border-line bg-bg-void p-6 text-center font-sans text-xs text-text-muted">
                No retained memory events found.
              </div>
            ) : (
              <div className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
                {timeline.map((ev) => (
                  <div
                    key={ev.event_id}
                    className="flex items-center justify-between rounded border border-line bg-bg-void px-3 py-2 text-xs font-mono"
                  >
                    <div className="flex items-center gap-2">
                      <span className="h-1.5 w-1.5 rounded-full bg-purple-400" />
                      <span className="font-bold text-purple-300">{ev.kind}</span>
                      <span className="text-line">|</span>
                      <span className="text-text-muted">{ev.zone}</span>
                      {ev.cause_tags && ev.cause_tags.length > 0 && (
                        <span className="text-text-muted/80">[{ev.cause_tags.join(", ")}]</span>
                      )}
                      {ev.notes && (
                        <span className="text-text-primary/80 truncate max-w-xs">{ev.notes}</span>
                      )}
                    </div>
                    <span className="shrink-0 text-[10px] text-text-muted">
                      {new Date(ev.ts).toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
