export const STATES = [
  "OBSERVED",
  "CANDIDATE",
  "VERIFIED",
  "RESPONSE_PROPOSED",
  "OPERATOR_APPROVED",
  "COORDINATION_IN_PROGRESS",
  "ACKNOWLEDGED",
  "EN_ROUTE",
  "ON_SCENE",
  "HANDED_OVER",
  "CLOSED",
] as const;

export type IncidentState = (typeof STATES)[number] | "REJECTED";

export interface Incident {
  id: string;
  state: IncidentState;
  zone: string;
  scenario: string;
  corroborator_score: number;
  skeptic_score: number;
  fused_score: number;
  confidence?: number;
  reasoning: string;
  media_file: string;
  timestamp: string;
  degraded?: boolean;
  field_status?: string | null;
  responder_id?: string | null;
  ack_channel?: string | null;
  ack_time?: string | null;
}

export interface AuditEntry {
  id: number;
  timestamp: string;
  actor: string;
  action: string;
  previous_hash: string;
  current_hash: string;
}

export interface SmsPayload {
  to: string;
  from: string;
  body: string;
  timestamp: string;
}

export interface ApproveResponse {
  status: string;
  sms_payload: SmsPayload;
}

export interface ChainVerifyResponse {
  valid: boolean;
  checked_blocks: number;
  broken_at: number | null;
}

export type ScenarioKey = "crash_zone04" | "false_alarm";

export type WsMessage =
  | { type: "incident_update"; incident: Incident; degraded?: boolean }
  | { type: "audit_entry"; entry: AuditEntry }
  | { type: "agent_reasoning_chunk"; agent: "CORROBORATOR" | "SKEPTIC" | "GOVERNOR"; text: string; done?: boolean }
  | { type: "audit_sync"; entries: AuditEntry[] };
