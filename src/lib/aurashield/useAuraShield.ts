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

export interface ReasoningLogItem {
  id: string;
  agent: "CORROBORATOR" | "SKEPTIC" | "GOVERNOR" | "SYSTEM";
  text: string;
  timestamp: string;
}

export function useAuraShield() {
  const [mode, setMode] = useState<Mode>(API_URL ? "live" : "mock");
  const [link, setLink] = useState<LinkStatus>("offline");
  const [incident, setIncident] = useState<Incident | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [sms, setSms] = useState<ApproveResponse["sms_payload"] | null>(null);
  const [chain, setChain] = useState<ChainVerifyResponse | null>(null);
  const [busy, setBusy] = useState(false);

  // P5: Reasoning Terminal and Operator Controls state
  const [reasoningLogs, setReasoningLogs] = useState<ReasoningLogItem[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [automationPaused, setAutomationPausedState] = useState(false);
  const [governorSensitivity, setGovernorSensitivityState] = useState(0.65);

  const wsRef = useRef<WebSocket | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const streamTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const auditId = useRef(0);

  const clearTimers = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    if (streamTimer.current) clearTimeout(streamTimer.current);
  };

  const addReasoningLog = useCallback(
    (agent: "CORROBORATOR" | "SKEPTIC" | "GOVERNOR" | "SYSTEM", text: string, timestamp?: string) => {
      const ts = timestamp ?? new Date().toTimeString().slice(0, 8);
      setReasoningLogs((prev) => [
        ...prev.slice(-199),
        { id: Math.random().toString(36).substring(2, 9), agent, text, timestamp: ts },
      ]);
      setIsStreaming(true);
      if (streamTimer.current) clearTimeout(streamTimer.current);
      streamTimer.current = setTimeout(() => {
        setIsStreaming(false);
      }, 1500);
    },
    [],
  );

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
        const msg = JSON.parse(ev.data as string) as
          | WsMessage
          | { type: "audit_sync"; entries: AuditEntry[] }
          | { type: "governor_sensitivity"; sensitivity: number }
          | { type: "automation_pause_status"; paused: boolean };
        if (msg.type === "incident_update") {
          const inc = {
            ...msg.incident,
            degraded: (msg as any).degraded ?? msg.incident.degraded ?? false,
          };
          setIncident(inc);
        }
        if (msg.type === "audit_entry")
          setAudit((prev) => (prev.some((e) => e.id === msg.entry.id) ? prev : [...prev, msg.entry]));
        if (msg.type === "audit_sync") setAudit(msg.entries);
        if (msg.type === "agent_reasoning_chunk") {
          addReasoningLog(msg.agent, msg.text, (msg as any).timestamp);
        }
        if (msg.type === "governor_sensitivity") {
          setGovernorSensitivityState(msg.sensitivity);
        }
        if (msg.type === "automation_pause_status") {
          setAutomationPausedState(msg.paused);
        }
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

  const refreshAudit = useCallback(async () => {
    if (!API_URL) return;
    try {
      const res = await fetch(`${API_URL}/audit/entries`);
      if (res.ok) {
        const data = (await res.json()) as AuditEntry[];
        setAudit(data);
      }
    } catch {
      /* ignore */
    }
  }, []);

  const tamperDemo = useCallback(async () => {
    if (mode === "live" && API_URL) {
      try {
        const res = await fetch(`${API_URL}/demo/tamper`, { method: "POST" });
        const data = (await res.json()) as { tampered_row_id: number; zone: string };
        await verifyChain();
        await refreshAudit();
        return data;
      } catch (e) {
        console.error("Tamper demo failed", e);
      }
    } else {
      if (audit.length > 2) {
        const targetIdx = Math.floor(audit.length / 2);
        const targetRow = audit[targetIdx];
        if (targetRow) {
          setAudit((prev) =>
            prev.map((item, idx) =>
              idx === targetIdx ? { ...item, action: `${item.action} [UNAUTHORIZED MUTATION]` } : item
            )
          );
          setChain({ valid: false, checked_blocks: targetIdx, broken_at: targetRow.id });
          return { tampered_row_id: targetRow.id, zone: "Zone 04" };
        }
      }
    }
    return null;
  }, [audit, mode, refreshAudit, verifyChain]);

  const restoreDemo = useCallback(async () => {
    if (mode === "live" && API_URL) {
      try {
        const res = await fetch(`${API_URL}/demo/restore`, { method: "POST" });
        const data = (await res.json()) as { restored_row_id: number };
        await verifyChain();
        await refreshAudit();
        return data;
      } catch (e) {
        console.error("Restore demo failed", e);
      }
    } else {
      setAudit((prev) =>
        prev.map((item) => ({
          ...item,
          action: item.action.replace(" [UNAUTHORIZED MUTATION]", ""),
        }))
      );
      setChain({ valid: true, checked_blocks: audit.length || MOCK_AUDIT_SEED.length, broken_at: null });
      return { restored_row_id: 0 };
    }
    return null;
  }, [audit.length, mode, refreshAudit, verifyChain]);

  const overrideReject = useCallback(
    async (incidentId: string, reason?: string) => {
      const overrideReason = reason || "Operator manual override: marked as false positive";
      if (mode === "live" && API_URL) {
        try {
          await fetch(`${API_URL}/incidents/${incidentId}/override-reject`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reason: overrideReason }),
          });
        } catch (e) {
          console.error("Override reject failed", e);
        }
        return;
      }
      // Mock mode override
      clearTimers();
      setIncident((prev) =>
        prev
          ? {
              ...prev,
              state: "REJECTED",
              reasoning: `REJECTED: Operator manual override — ${overrideReason}`,
            }
          : prev
      );
      pushAudit("operator_1", `OPERATOR_OVERRIDE_REJECT: ${incidentId} — ${overrideReason}`);
      addReasoningLog("GOVERNOR", `OVERRIDE: Operator rejected incident ${incidentId}. State -> REJECTED.`);
      setBusy(false);
    },
    [addReasoningLog, mode, pushAudit],
  );

  const setGovernorSensitivity = useCallback(
    async (val: number) => {
      const clamped = Math.max(0.5, Math.min(0.95, Number(val.toFixed(2))));
      setGovernorSensitivityState(clamped);
      if (mode === "live" && API_URL) {
        try {
          await fetch(`${API_URL}/governor/sensitivity`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sensitivity: clamped }),
          });
        } catch {
          /* fallback */
        }
      } else {
        pushAudit("operator_1", `GOVERNOR_SENSITIVITY_SET: threshold=${clamped.toFixed(2)}`);
        addReasoningLog("GOVERNOR", `Governor sensitivity updated to ${clamped.toFixed(2)}`);
      }
    },
    [addReasoningLog, mode, pushAudit],
  );

  const setAutomationPaused = useCallback(
    async (paused: boolean) => {
      setAutomationPausedState(paused);
      if (mode === "live" && API_URL) {
        try {
          await fetch(`${API_URL}/governor/pause`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ paused }),
          });
        } catch {
          /* fallback */
        }
      } else {
        pushAudit("operator_1", paused ? "AUTOMATION_PAUSED_BY_OPERATOR" : "AUTOMATION_RESUMED_BY_OPERATOR");
        addReasoningLog(
          "GOVERNOR",
          paused
            ? "AUTOMATION PAUSED BY OPERATOR: incident awaiting clearance or unpause."
            : "AUTOMATION RESUMED BY OPERATOR.",
        );
      }
    },
    [addReasoningLog, mode, pushAudit],
  );

  const clearReasoningLogs = useCallback(() => {
    setReasoningLogs([]);
  }, []);

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
    refreshAudit,
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
  };
}
