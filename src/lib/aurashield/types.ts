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

export type ScenarioKey = "crash_zone04" | "false_alarm" | "glare_ambiguous";

export interface Precedent {
  text: string;
  source: "hindsight" | "local-fallback";
  relevance?: number;
  ts?: string;
  kind?: string;
  zone?: string;
  cause_tags?: string[];
}

export interface MemoryAdjustment {
  applied: boolean;
  corr_delta: number;
  skep_delta: number;
  delta: number;
  dominant?: string | null;
  dominant_count?: number;
  reason?: string;
}

export interface MemoryScores {
  corr: number;
  skep: number;
  fused: number;
}

export interface MemoryInfo {
  enabled: boolean;
  used: boolean;
  source: string;
  precedents: Precedent[];
  adjustment: MemoryAdjustment;
  pre_memory_scores: MemoryScores;
  post_memory_scores: MemoryScores;
  suppressed_by_memory?: boolean;
}

export interface MemoryStatus {
  enabled: boolean;
  hindsight_reachable: boolean;
  bank_id: string;
  events_in_ledger: number;
  last_error?: string | null;
  circuit_breaker_open?: boolean;
}

export interface MemoryEvent {
  event_id: string;
  ts: string;
  kind: string;
  incident_id: string;
  zone: string;
  scenario: string;
  cause_tags?: string[];
  operator_action?: string | null;
  outcome?: string | null;
  confidence?: number;
  corr_score?: number | null;
  skeptic_score?: number | null;
  fused_score?: number | null;
  notes?: string | null;
}

export interface LearningCurvePoint {
  run: number;
  scenario: string;
  pre_memory_fused: number;
  post_memory_fused: number;
  verdict: string;
  precedents: number;
  timestamp?: string;
}

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
  memory?: MemoryInfo | null;
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

export type WsMessage =
  | { type: "incident_update"; incident: Incident; degraded?: boolean; memory?: MemoryInfo }
  | { type: "audit_entry"; entry: AuditEntry }
  | {
      type: "agent_reasoning_chunk";
      agent: "CORROBORATOR" | "SKEPTIC" | "GOVERNOR" | "MEMORY" | "SYSTEM";
      text: string;
      done?: boolean;
      timestamp?: string;
    }
  | { type: "audit_sync"; entries: AuditEntry[] }
  | { type: "memory_status"; status: MemoryStatus }
  | { type: "memory_event"; event: MemoryEvent }
  | { type: "governor_sensitivity"; sensitivity: number }
  | { type: "automation_pause_status"; paused: boolean };
