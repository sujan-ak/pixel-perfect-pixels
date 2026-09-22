import { useEffect, useRef } from "react";
import { CheckCircle2, Link2Off, ShieldQuestion } from "lucide-react";
import type { AuditEntry, ChainVerifyResponse } from "@/lib/aurashield/types";

export function AuditLedger({
  entries,
  chain,
  onVerify,
}: {
  entries: AuditEntry[];
  chain: ChainVerifyResponse | null;
  onVerify: () => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [entries.length]);

  return (
    <div className="panel flex flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <span className="font-mono text-[11px] tracking-[0.2em] text-muted-foreground">
          IMMUTABLE AUDIT LEDGER
        </span>
        <div className="flex items-center gap-3">
          {chain && (
            <span
              className={`flex items-center gap-1.5 font-mono text-[11px] ${chain.valid ? "text-success" : "text-critical"}`}
            >
              {chain.valid ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Link2Off className="h-3.5 w-3.5" />}
              {chain.valid
                ? `CHAIN INTACT · ${chain.checked_blocks} BLOCKS`
                : `CHAIN BROKEN AT BLOCK ${chain.broken_at}`}
            </span>
          )}
          <button
            onClick={onVerify}
            className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 font-mono text-[11px] text-foreground transition-colors hover:border-success hover:text-success"
          >
            <ShieldQuestion className="h-3.5 w-3.5" />
            VERIFY CHAIN INTEGRITY
          </button>
        </div>
      </div>

      <div ref={scroller} className="h-44 overflow-y-auto px-4 py-2 font-mono text-[11px] leading-6">
        {entries.length === 0 && <div className="text-neutral">// ledger empty — trigger a scenario</div>}
        {entries.map((e) => (
          <div key={e.id} className="flex flex-wrap gap-x-3 text-muted-foreground">
            <span className="text-neutral">{new Date(e.timestamp).toISOString().slice(11, 19)}</span>
            <span className="text-warning">{e.actor}</span>
            <span className="text-foreground">{e.action}</span>
            <span className="text-success/70">{e.current_hash}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
