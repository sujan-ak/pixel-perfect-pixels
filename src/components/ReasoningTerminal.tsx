import { useEffect, useRef } from "react";
import { Terminal, Trash2, Zap } from "lucide-react";
import type { ReasoningLogItem } from "@/lib/aurashield/useAuraShield";

interface ReasoningTerminalProps {
  logs: ReasoningLogItem[];
  isStreaming: boolean;
  onClear: () => void;
}

export function ReasoningTerminal({ logs, isStreaming, onClear }: ReasoningTerminalProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, isStreaming]);

  const getAgentColor = (agent: string) => {
    switch (agent) {
      case "CORROBORATOR":
        return "text-emerald-400 font-bold";
      case "SKEPTIC":
        return "text-rose-400 font-bold";
      case "GOVERNOR":
        return "text-amber-400 font-bold";
      case "MEMORY":
        return "text-purple-400 font-bold";
      default:
        return "text-signal-data font-bold";
    }
  };

  return (
    <div className="flex flex-col rounded border border-line bg-bg-panel overflow-hidden">
      {/* Terminal Title Bar */}
      <div className="flex items-center justify-between border-b border-line bg-bg-panel-raised px-4 py-2">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-signal-data" />
          <span className="font-sans text-label font-semibold text-text-primary">
            Agent Reasoning Terminal
          </span>
          <span className="text-line">/</span>
          <span className="font-sans text-xs text-text-muted">Adversarial consensus engine</span>
        </div>

        <div className="flex items-center gap-3">
          {isStreaming ? (
            <span className="flex items-center gap-1.5 rounded-full border border-signal-verified/40 bg-signal-verified/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-signal-verified">
              <Zap className="h-3 w-3 animate-bounce" />
              <span>STREAMING LLM</span>
            </span>
          ) : (
            <span className="flex items-center gap-1.5 rounded-full border border-line bg-bg-void px-2 py-0.5 font-mono text-[10px] text-text-muted">
              <span className="h-1.5 w-1.5 rounded-full bg-text-muted" />
              <span>IDLE</span>
            </span>
          )}

          <span className="font-mono text-xs text-text-muted">{logs.length} / 200 lines</span>

          <button
            onClick={onClear}
            title="Clear terminal"
            className="flex items-center gap-1 rounded border border-line bg-bg-panel px-2 py-0.5 font-sans text-xs text-text-muted transition-colors hover:border-text-primary hover:text-text-primary"
          >
            <Trash2 className="h-3 w-3" />
            <span>Clear</span>
          </button>
        </div>
      </div>

      {/* Monospace Terminal Body */}
      <div
        ref={scrollRef}
        className="h-48 overflow-y-auto bg-[#07090e] p-3 font-mono text-xs leading-relaxed selection:bg-signal-data/30"
      >
        {logs.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center text-text-muted">
            <p className="text-text-muted">[SYSTEM] Awaiting agent verification stream...</p>
            <p className="mt-1 text-[11px] text-text-muted/60">
              Trigger a scenario or adjust Governor Sensitivity to observe adversarial reasoning.
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            {logs.map((item) => (
              <div key={item.id} className="flex items-start gap-2 break-words">
                <span className="shrink-0 text-text-muted opacity-60">{item.timestamp}</span>
                <span className={`shrink-0 ${getAgentColor(item.agent)}`}>[{item.agent}]</span>
                <span className="text-text-primary/90">{item.text}</span>
              </div>
            ))}

            {isStreaming && (
              <div className="flex items-center gap-2 pt-1 text-signal-data">
                <span className="text-text-muted opacity-60">...</span>
                <span className="inline-block h-3.5 w-2 animate-pulse bg-signal-data" />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
