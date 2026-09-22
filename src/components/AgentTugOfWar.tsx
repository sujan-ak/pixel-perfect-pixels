import { motion } from "framer-motion";
import { ShieldCheck, ShieldAlert } from "lucide-react";
import type { Incident } from "@/lib/aurashield/types";
import { cn } from "@/lib/utils";

const FUSED_THRESHOLD = 0.8;
const MARGIN_THRESHOLD = 0.35;

export function AgentTugOfWar({ incident }: { incident: Incident | null }) {
  const corroborator = incident?.corroborator_score ?? 0;
  const skeptic = incident?.skeptic_score ?? 0;
  const fused = incident?.fused_score ?? 0;
  const margin = corroborator - skeptic;
  const total = corroborator + skeptic || 1;
  const pull = (corroborator / total) * 100;
  const verified = fused >= FUSED_THRESHOLD && margin > MARGIN_THRESHOLD;

  return (
    <div className="panel flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] tracking-[0.2em] text-muted-foreground">
          AGENT ADJUDICATION
        </span>
        <span
          className={cn(
            "rounded-md border px-2 py-0.5 font-mono text-[11px]",
            verified ? "border-success text-success" : "border-neutral text-neutral",
          )}
        >
          {verified ? "THRESHOLD MET" : "BELOW THRESHOLD"}
        </span>
      </div>

      <div className="flex items-end justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-success" />
          <div>
            <div className="font-mono text-[11px] text-muted-foreground">CORROBORATOR</div>
            <div className="font-mono text-2xl text-success">{corroborator.toFixed(2)}</div>
          </div>
        </div>
        <div className="text-right">
          <div className="font-mono text-[11px] text-muted-foreground">FUSED</div>
          <div
            className={cn(
              "font-mono text-2xl",
              verified ? "text-success" : fused < 0 ? "text-critical" : "text-warning",
            )}
          >
            {fused.toFixed(2)}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-right">
            <div className="font-mono text-[11px] text-muted-foreground">SKEPTIC</div>
            <div className="font-mono text-2xl text-critical">{skeptic.toFixed(2)}</div>
          </div>
          <ShieldAlert className="h-4 w-4 text-critical" />
        </div>
      </div>

      <div className="relative h-7 overflow-hidden rounded-md border border-border bg-background">
        <motion.div
          className="absolute inset-y-0 left-0 bg-success/35"
          animate={{ width: `${pull}%` }}
          transition={{ type: "spring", stiffness: 90, damping: 18 }}
        />
        <motion.div
          className="absolute inset-y-0 right-0 bg-critical/35"
          animate={{ width: `${100 - pull}%` }}
          transition={{ type: "spring", stiffness: 90, damping: 18 }}
        />
        <motion.div
          className="absolute inset-y-0 w-0.5 bg-foreground"
          animate={{ left: `${pull}%` }}
          transition={{ type: "spring", stiffness: 90, damping: 18 }}
        />
        <div
          className="absolute inset-y-0 border-l border-dashed border-warning"
          style={{ left: `${FUSED_THRESHOLD * 100}%` }}
        />
      </div>

      <div className="flex justify-between font-mono text-[10px] text-muted-foreground">
        <span>MARGIN {margin.toFixed(2)} / REQ &gt; {MARGIN_THRESHOLD}</span>
        <span>FUSED REQ ≥ {FUSED_THRESHOLD.toFixed(2)}</span>
      </div>

      <div className="mt-auto rounded-md border border-border bg-background p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
        {incident?.reasoning ?? "AWAITING INCIDENT STREAM…"}
      </div>
    </div>
  );
}
