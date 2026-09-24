import { useEffect, useRef } from "react";
import { CheckCircle2, Link2Off, ShieldCheck } from "lucide-react";
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
  const lastEntryId = entries.length > 0 ? entries[entries.length - 1]?.id ?? 0 : 0;

  useEffect(() => {
    if (scroller.current) {
      scroller.current.scrollTo({
        top: scroller.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [entries.length]);

  return (
    <div className="rounded border border-line bg-bg-panel flex flex-col">
      {/* Ledger Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="font-sans text-panel-header text-text-primary">
            Immutable audit ledger
          </span>
          <span className="font-sans text-label text-text-muted">
            / SHA-256 tamper-evident chain
          </span>
        </div>

        <div className="flex items-center gap-3">
          {chain && (
            <div className="flex items-center gap-1.5 font-mono text-label">
              {chain.valid ? (
                <span className="flex items-center gap-1.5 rounded border border-signal-verified/40 bg-signal-verified/10 px-2 py-0.5 text-signal-verified font-medium">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Chain intact &middot; {chain.checked_blocks} blocks verified
                </span>
              ) : (
                <span className="flex items-center gap-1.5 rounded border border-signal-rejected bg-signal-rejected/15 px-2 py-0.5 text-signal-rejected font-medium">
                  <Link2Off className="h-3.5 w-3.5" />
                  Chain broken at block #{chain.broken_at}
                </span>
              )}
            </div>
          )}

          <button
            onClick={onVerify}
            className="flex items-center gap-1.5 rounded border border-line bg-bg-panel-raised px-2.5 py-1 font-sans text-label text-text-primary transition-colors hover:border-signal-verified hover:text-signal-verified focus-visible:ring-1 focus-visible:ring-signal-data"
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Verify chain integrity</span>
          </button>
        </div>
      </div>

      {/* Monospace Dense Ledger Table */}
      <div
        ref={scroller}
        className="max-h-56 overflow-y-auto font-mono text-label leading-relaxed select-text"
      >
        <table className="w-full border-collapse text-left">
          <thead className="sticky top-0 z-10 border-b border-line bg-bg-panel-raised/95 backdrop-blur font-sans text-label text-text-muted">
            <tr>
              <th className="py-1.5 pl-4 pr-2 font-normal w-12">#</th>
              <th className="py-1.5 px-2 font-normal w-24">Time (UTC)</th>
              <th className="py-1.5 px-2 font-normal w-36">Actor</th>
              <th className="py-1.5 px-2 font-normal">Action</th>
              <th className="py-1.5 pl-2 pr-4 font-normal text-right">Hash chain (prev &rarr; current)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line/40">
            {entries.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-6 text-center text-text-muted font-sans text-body">
                  Ledger empty &mdash; trigger a scenario to initialize hash chain
                </td>
              </tr>
            ) : (
              entries.map((e, i) => {
                const isLatest = i === entries.length - 1;
                const prevHash = i === 0 ? "0000...0000" : (entries[i - 1]?.current_hash ?? "0000...0000");
                return (
                  <tr
                    key={e.id}
                    className={`transition-colors hover:bg-bg-panel-raised/60 ${
                      isLatest ? "audit-row-enter" : ""
                    }`}
                  >
                    {/* Index */}
                    <td className="py-1.5 pl-4 pr-2 text-text-muted">{String(e.id).padStart(3, "0")}</td>

                    {/* Timestamp */}
                    <td className="py-1.5 px-2 text-text-muted">
                      {new Date(e.timestamp).toISOString().slice(11, 19)}
                    </td>

                    {/* Actor */}
                    <td className="py-1.5 px-2">
                      <span
                        className={
                          e.actor === "system"
                            ? "text-text-muted"
                            : e.actor === "operator_1"
                            ? "text-signal-pending font-medium"
                            : "text-signal-verified font-medium"
                        }
                      >
                        {e.actor}
                      </span>
                    </td>

                    {/* Action */}
                    <td className="py-1.5 px-2 text-text-primary">
                      {e.action}
                    </td>

                    {/* Literal Hash Chain (prev -> curr) */}
                    <td className="py-1.5 pl-2 pr-4 text-right">
                      <span className="inline-flex items-center gap-1.5 rounded border border-line/60 bg-bg-void px-2 py-0.5 font-mono">
                        <span className="text-text-muted/80">{prevHash}</span>
                        <span className="text-line">&rarr;</span>
                        {/* Live WS hash landing styled in cyan signal-data */}
                        <span className="text-signal-data font-medium">{e.current_hash}</span>
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
