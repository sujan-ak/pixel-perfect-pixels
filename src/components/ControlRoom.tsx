import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CarFront, MessageSquare, Power, Siren, X } from "lucide-react";
import { AgentTugOfWar } from "./AgentTugOfWar";
import { AuditLedger } from "./AuditLedger";
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
    reset,
  } = useAuraShield();

  const awaitingClearance = incident?.state === "RESPONSE_PROPOSED";

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3">
        <div className="flex items-center gap-2">
          <Siren className="h-5 w-5 text-critical" />
          <h1 className="font-mono text-sm tracking-[0.3em]">AURASHIELD</h1>
          <span className="font-mono text-[11px] text-muted-foreground">/ INCIDENT CONTROL ROOM</span>
        </div>
        <div className="flex items-center gap-2 font-mono text-[11px]">
          <span
            className={`rounded-md border px-2 py-1 ${
              mode === "live"
                ? link === "online"
                  ? "border-success text-success"
                  : "border-critical text-critical"
                : "border-warning text-warning"
            }`}
          >
            {mode === "live" ? `LIVE BACKEND · ${link.toUpperCase()}` : "MOCK DATA MODE"}
          </span>
          <button
            onClick={() => {
              reset();
              setMode(mode === "mock" ? "live" : "mock");
            }}
            className="flex items-center gap-1.5 rounded-md border border-border px-2 py-1 transition-colors hover:border-foreground"
          >
            <Power className="h-3.5 w-3.5" />
            SWITCH TO {mode === "mock" ? "LIVE" : "MOCK"}
          </button>
        </div>
      </header>

      <main className="mx-auto flex max-w-[1400px] flex-col gap-4 p-5">
        <StateTracker state={incident?.state ?? null} />

        <div className="flex flex-wrap gap-2">
          <button
            disabled={busy}
            onClick={() => triggerScenario("crash_zone04")}
            className="flex items-center gap-2 rounded-md border border-critical/60 px-3 py-2 font-mono text-[11px] text-critical transition-colors hover:bg-critical/10 disabled:opacity-40"
          >
            <CarFront className="h-4 w-4" />
            TRIGGER CRASH SCENARIO
          </button>
          <button
            disabled={busy}
            onClick={() => triggerScenario("false_alarm")}
            className="flex items-center gap-2 rounded-md border border-warning/60 px-3 py-2 font-mono text-[11px] text-warning transition-colors hover:bg-warning/10 disabled:opacity-40"
          >
            <AlertTriangle className="h-4 w-4" />
            TRIGGER FALSE ALARM SCENARIO
          </button>
          <button
            onClick={reset}
            className="rounded-md border border-border px-3 py-2 font-mono text-[11px] text-muted-foreground transition-colors hover:border-foreground hover:text-foreground"
          >
            RESET CONSOLE
          </button>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <VideoFeed incident={incident} />
          <AgentTugOfWar incident={incident} />
        </div>

        <AnimatePresence>
          {awaitingClearance && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              className="panel glow-critical flex flex-wrap items-center justify-between gap-3 p-4"
            >
              <div>
                <motion.div
                  animate={{ opacity: [1, 0.6, 1] }}
                  transition={{ duration: 1.6, repeat: Infinity }}
                  className="font-mono text-sm tracking-[0.2em] text-critical"
                >
                  AWAITING OPERATOR CLEARANCE
                </motion.div>
                <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                  {incident?.zone} · dispatch requires a human decision before SMS is sent.
                </p>
              </div>
              <button
                onClick={approveDispatch}
                className="rounded-md bg-critical px-5 py-2.5 font-mono text-[12px] tracking-widest text-background transition-opacity hover:opacity-90"
              >
                APPROVE DISPATCH
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        <AuditLedger entries={audit} chain={chain} onVerify={verifyChain} />
      </main>

      <AnimatePresence>
        {sms && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4"
          >
            <motion.div
              initial={{ scale: 0.96 }}
              animate={{ scale: 1 }}
              className="panel glow-success w-full max-w-lg p-5"
            >
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 font-mono text-[12px] tracking-[0.2em] text-success">
                  <MessageSquare className="h-4 w-4" />
                  SMS DISPATCHED
                </span>
                <button onClick={() => setSms(null)} className="text-muted-foreground hover:text-foreground">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-4 space-y-2 rounded-md border border-border bg-background p-3 font-mono text-[11px]">
                <div>
                  <span className="text-muted-foreground">TO: </span>
                  {sms.to}
                </div>
                <div>
                  <span className="text-muted-foreground">FROM: </span>
                  {sms.from}
                </div>
                <div>
                  <span className="text-muted-foreground">SENT: </span>
                  {sms.timestamp}
                </div>
                <div className="border-t border-border pt-2 leading-relaxed">{sms.body}</div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
