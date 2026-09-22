import { useCallback, useEffect, useRef, useState } from "react";
import { MOCK_AUDIT_SEED, MOCK_SCENARIOS, shortHash } from "./mockData";
import type {
  ApproveResponse,
  AuditEntry,
  ChainVerifyResponse,
  Incident,
  ScenarioKey,
  WsMessage,
} from "./types";

const API_URL = import.meta.env["VITE_API_URL"] as string | undefined;

export type Mode = "mock" | "live";
export type LinkStatus = "offline" | "connecting" | "online";

export function useAuraShield() {
  const [mode, setMode] = useState<Mode>(API_URL ? "live" : "mock");
  const [link, setLink] = useState<LinkStatus>("offline");
  const [incident, setIncident] = useState<Incident | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [sms, setSms] = useState<ApproveResponse["sms_payload"] | null>(null);
  const [chain, setChain] = useState<ChainVerifyResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const auditId = useRef(0);

  const clearTimers = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  };

  const pushAudit = useCallback((actor: string, action: string) => {
    setAudit((prev) => {
      const previous_hash = prev.at(-1)?.current_hash ?? "0000...0000";
      auditId.current += 1;
      return [
        ...prev,
        {
          id: auditId.current,
          timestamp: new Date().toISOString(),
          actor,
          action,
          previous_hash,
          current_hash: shortHash(),
        },
      ];
    });
  }, []);

  // Live WebSocket connection
  useEffect(() => {
    if (mode !== "live" || !API_URL) {
      setLink("offline");
      return;
    }
    setLink("connecting");
    const url = API_URL.replace(/^http/, "ws") + "/ws";
    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch {
      setLink("offline");
      return;
    }
    wsRef.current = ws;
    ws.onopen = () => setLink("online");
    ws.onclose = () => setLink("offline");
    ws.onerror = () => setLink("offline");
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string) as WsMessage;
        if (msg.type === "incident_update") setIncident(msg.incident);
        if (msg.type === "audit_entry")
          setAudit((prev) => (prev.some((e) => e.id === msg.entry.id) ? prev : [...prev, msg.entry]));
      } catch {
        /* ignore malformed frame */
      }
    };
    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [mode]);

  useEffect(() => () => clearTimers(), []);

  const reset = useCallback(() => {
    clearTimers();
    setIncident(null);
    setAudit([]);
    setSms(null);
    setChain(null);
    auditId.current = 0;
  }, []);

  const triggerScenario = useCallback(
    async (scenario: ScenarioKey) => {
      reset();
      setBusy(true);
      if (mode === "live" && API_URL) {
        try {
          await fetch(`${API_URL}/incidents/trigger`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ scenario }),
          });
        } catch {
          /* stream will stay empty if backend is unreachable */
        }
        setBusy(false);
        return;
      }
      const seq = MOCK_SCENARIOS[scenario];
      seq.forEach((step, i) => {
        timers.current.push(
          setTimeout(() => {
            setIncident(step);
            pushAudit(
              i === 0 ? "system" : "safety_governor",
              i === 0
                ? `INCIDENT_CREATED: ${step.id}`
                : `STATE_TRANSITION: ${seq[i - 1]?.state} -> ${step.state}`,
            );
            if (i === seq.length - 1) setBusy(false);
          }, i * 1400),
        );
      });
    },
    [mode, pushAudit, reset],
  );

  const approveDispatch = useCallback(async () => {
    if (!incident) return;
    setBusy(true);
    if (mode === "live" && API_URL) {
      try {
        const res = await fetch(`${API_URL}/incidents/${incident.id}/approve`, { method: "POST" });
        const data = (await res.json()) as ApproveResponse;
        setSms(data.sms_payload);
      } catch {
        /* backend unreachable */
      }
      setBusy(false);
      return;
    }
    const after: Incident["state"][] = [
      "OPERATOR_APPROVED",
      "COORDINATION_IN_PROGRESS",
      "ACKNOWLEDGED",
      "CLOSED",
    ];
    pushAudit("operator_1", `APPROVE_DISPATCH: ${incident.id}`);
    setSms({
      to: "+919876543210",
      from: "AURASHIELD",
      body: `VERIFIED INCIDENT ${incident.zone} — severity ${incident.corroborator_score.toFixed(2)} — dispatch requested`,
      timestamp: new Date().toISOString(),
    });
    after.forEach((state, i) => {
      timers.current.push(
        setTimeout(() => {
          setIncident((prev) => (prev ? { ...prev, state, reasoning: `${state}: dispatch pipeline` } : prev));
          pushAudit("dispatch_coordinator", `STATE_TRANSITION: -> ${state}`);
          if (i === after.length - 1) setBusy(false);
        }, (i + 1) * 1200),
      );
    });
  }, [incident, mode, pushAudit]);

  const verifyChain = useCallback(async () => {
    if (mode === "live" && API_URL) {
      try {
        const res = await fetch(`${API_URL}/audit/verify`);
        setChain((await res.json()) as ChainVerifyResponse);
      } catch {
        setChain({ valid: false, checked_blocks: 0, broken_at: 0 });
      }
      return;
    }
    setChain({ valid: true, checked_blocks: audit.length || MOCK_AUDIT_SEED.length, broken_at: null });
  }, [audit.length, mode]);

  return {
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
  };
}
