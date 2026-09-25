import { useEffect, useRef, useState } from "react";
import {
  AlertOctagon,
  CheckCircle2,
  Link2Off,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import type { AuditEntry, ChainVerifyResponse } from "@/lib/aurashield/types";

export function AuditLedger({
  entries,
  chain,
  onVerify,
  onTamper,
  onRestore,
}: {
  entries: AuditEntry[];
  chain: ChainVerifyResponse | null;
  onVerify: () => void;
  onTamper?: () => Promise<{ tampered_row_id: number; zone: string } | null | void>;
  onRestore?: () => Promise<{ restored_row_id: number } | null | void>;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const tamperedRowRef = useRef<HTMLTableRowElement>(null);
  const [tamperedRowId, setTamperedRowId] = useState<number | null>(null);
  const [isTampering, setIsTampering] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [restoreSweep, setRestoreSweep] = useState(false);

  // Keep track of broken state from chain if available
  const isChainBroken = chain && !chain.valid;
  const effectiveBrokenId = tamperedRowId ?? (isChainBroken ? chain.broken_at : null);

  useEffect(() => {
    if (scroller.current && !effectiveBrokenId) {
      scroller.current.scrollTo({
        top: scroller.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [entries.length, effectiveBrokenId]);

  // Scroll to tampered row when rupture happens
  useEffect(() => {
    if (effectiveBrokenId && tamperedRowRef.current) {
      tamperedRowRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [effectiveBrokenId]);

  const handleTamper = async () => {
    if (!onTamper || isTampering) return;
    setIsTampering(true);
    try {
      const res = await onTamper();
      if (res && res.tampered_row_id) {
        setTamperedRowId(res.tampered_row_id);
      }
    } finally {
      setIsTampering(false);
    }
  };

  const handleRestore = async () => {
    if (!onRestore || isRestoring) return;
    setIsRestoring(true);
    try {
      await onRestore();
      setRestoreSweep(true);
      setTamperedRowId(null);
      setTimeout(() => {
        setRestoreSweep(false);
      }, 1000);
    } finally {
      setIsRestoring(false);
    }
  };

  return (
    <div className="rounded border border-line bg-bg-panel flex flex-col overflow-hidden">
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
                <span className="flex items-center gap-1.5 rounded border border-signal-verified/40 bg-signal-verified/10 px-2.5 py-0.5 text-signal-verified font-medium">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Chain intact &middot; {chain.checked_blocks} blocks verified
                </span>
              ) : (
                <span className="flex items-center gap-1.5 rounded border border-signal-rejected bg-signal-rejected/20 px-2.5 py-0.5 text-signal-rejected font-semibold animate-pulse shadow-[0_0_10px_rgba(255,92,92,0.3)]">
                  <Link2Off className="h-3.5 w-3.5" />
                  valid: false &mdash; broken at block #{chain.broken_at}
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
        className="max-h-60 overflow-y-auto font-mono text-label leading-relaxed select-text"
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

                const isTampered =
                  effectiveBrokenId !== null &&
                  (e.id === effectiveBrokenId || (isChainBroken && chain?.broken_at === e.id));

                const isDownstream =
                  effectiveBrokenId !== null &&
                  e.id > effectiveBrokenId;

                return (
                  <tr
                    key={e.id}
                    ref={isTampered ? tamperedRowRef : undefined}
                    className={`transition-all duration-300 ${
                      restoreSweep
                        ? "bg-signal-verified/15 text-signal-verified"
                        : isTampered
                        ? "bg-signal-rejected/25 border-l-4 border-l-signal-rejected font-medium"
                        : isDownstream
                        ? "opacity-35 grayscale border-l-2 border-l-line/40 select-none hover:opacity-50"
                        : isLatest
                        ? "audit-row-enter hover:bg-bg-panel-raised/60"
                        : "hover:bg-bg-panel-raised/60"
                    }`}
                  >
                    {/* Index */}
                    <td className={`py-1.5 pl-4 pr-2 ${isTampered ? "text-signal-rejected font-bold" : "text-text-muted"}`}>
                      {String(e.id).padStart(3, "0")}
                    </td>

                    {/* Timestamp */}
                    <td className={`py-1.5 px-2 ${isTampered ? "text-signal-rejected" : "text-text-muted"}`}>
                      {new Date(e.timestamp).toISOString().slice(11, 19)}
                    </td>

                    {/* Actor */}
                    <td className="py-1.5 px-2">
                      <span
                        className={
                          isTampered
                            ? "text-signal-rejected font-bold"
                            : e.actor === "system"
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
                    <td className="py-1.5 px-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={isTampered ? "text-signal-rejected font-bold" : "text-text-primary"}>
                          {e.action}
                        </span>
                        {isTampered && (
                          <span className="inline-flex items-center gap-1 rounded border border-signal-rejected bg-signal-rejected/30 px-1.5 py-0.2 font-mono text-[10px] font-bold text-signal-rejected animate-bounce">
                            <Link2Off className="h-3 w-3" />
                            MUTATION DETECTED
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Literal Hash Chain (prev -> curr) */}
                    <td className="py-1.5 pl-2 pr-4 text-right">
                      {isTampered ? (
                        <span className="inline-flex items-center gap-1.5 rounded border border-signal-rejected bg-signal-rejected/25 px-2 py-0.5 font-mono text-signal-rejected font-bold shadow-[0_0_12px_rgba(255,92,92,0.4)]">
                          <span>{prevHash}</span>
                          <Link2Off className="h-3.5 w-3.5 text-signal-rejected animate-pulse" />
                          <span className="line-through opacity-70">{e.current_hash}</span>
                          <span className="text-[10px] uppercase tracking-wide bg-signal-rejected text-bg-void px-1 rounded ml-1">
                            Broken
                          </span>
                        </span>
                      ) : isDownstream ? (
                        <div className="inline-flex items-center gap-2">
                          <span className="inline-flex items-center gap-1 rounded border border-line/50 bg-bg-void px-1.5 py-0.5 font-mono text-[10px] text-text-muted italic">
                            <ShieldAlert className="h-3 w-3 text-signal-pending" />
                            <span>Integrity unverified</span>
                          </span>
                          <span className="inline-flex items-center gap-1.5 rounded border border-line/40 bg-bg-void/50 px-2 py-0.5 font-mono opacity-60">
                            <span className="text-text-muted/60">{prevHash}</span>
                            <span className="text-line">&rarr;</span>
                            <span className="text-text-primary/60">{e.current_hash}</span>
                          </span>
                        </div>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 rounded border border-line/60 bg-bg-void px-2 py-0.5 font-mono">
                          <span className="text-text-muted/80">{prevHash}</span>
                          <span className="text-line">&rarr;</span>
                          <span className="text-text-primary font-medium">{e.current_hash}</span>
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Distinct Judge-Facing Demonstration Bottom Strip */}
      <div className="border-t border-line/80 bg-bg-panel-raised/50 px-4 py-2 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="rounded border border-signal-rejected/50 bg-signal-rejected/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-signal-rejected uppercase tracking-wider">
            Demo &middot; Tamper-Evidence
          </span>
          <span className="font-sans text-label text-text-muted">
            Mutate an immutable historical record to trigger immediate SHA-256 cascade failure.
          </span>
        </div>

        <div className="flex items-center gap-3">
          {isChainBroken ? (
            <>
              <div className="flex items-center gap-2 rounded border border-signal-rejected bg-signal-rejected/15 px-3 py-1 font-mono text-label text-signal-rejected font-semibold">
                <Link2Off className="h-4 w-4 animate-pulse shrink-0" />
                <span>valid: false &mdash; broken at block #{chain?.broken_at}</span>
              </div>
              <button
                onClick={handleRestore}
                disabled={isRestoring}
                className="flex items-center gap-1.5 rounded border border-signal-verified/60 bg-signal-verified/15 px-3 py-1 font-sans text-label font-semibold text-signal-verified hover:bg-signal-verified/25 active:scale-95 transition-all shadow-[0_0_10px_rgba(61,220,132,0.2)] disabled:opacity-50"
              >
                <RotateCcw className={`h-3.5 w-3.5 ${isRestoring ? "animate-spin" : ""}`} />
                <span>Restore Chain</span>
              </button>
            </>
          ) : (
            <button
              onClick={handleTamper}
              disabled={isTampering || entries.length < 3}
              className="flex items-center gap-1.5 rounded border border-signal-rejected/60 bg-signal-rejected/10 px-3 py-1 font-sans text-label font-semibold text-signal-rejected hover:bg-signal-rejected/20 active:scale-95 transition-all disabled:opacity-40"
            >
              <AlertOctagon className="h-3.5 w-3.5" />
              <span>{isTampering ? "Mutating block..." : "Attempt Tamper (Demo)"}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
