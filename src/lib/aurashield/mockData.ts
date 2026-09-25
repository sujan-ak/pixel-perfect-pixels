import type { AuditEntry, Incident, ScenarioKey } from "./types";

export function buildMockScenario(scenario: ScenarioKey): Incident[] {
  const now = new Date();
  const t = (offsetSec: number) => new Date(now.getTime() + offsetSec * 1000).toISOString();

  if (scenario === "crash_zone04") {
    return [
      {
        id: "inc_001",
        state: "OBSERVED",
        zone: "Zone 04",
        scenario: "crash_zone04",
        corroborator_score: 0.2,
        skeptic_score: 0.1,
        fused_score: 0.1,
        confidence: 0.9,
        reasoning: "OBSERVED: anomaly detected, awaiting agent scoring",
        media_file: "traffic_crash_zone04.mp4",
        timestamp: t(0),
      },
      {
        id: "inc_001",
        state: "CANDIDATE",
        zone: "Zone 04",
        scenario: "crash_zone04",
        corroborator_score: 0.65,
        skeptic_score: 0.2,
        fused_score: 0.45,
        confidence: 0.9,
        reasoning: "CANDIDATE: initial scoring in progress",
        media_file: "traffic_crash_zone04.mp4",
        timestamp: t(1),
      },
      {
        id: "inc_001",
        state: "VERIFIED",
        zone: "Zone 04",
        scenario: "crash_zone04",
        corroborator_score: 0.91,
        skeptic_score: 0.14,
        fused_score: 0.77,
        confidence: 0.9,
        reasoning:
          "VERIFIED: fused score 0.77, corroborator 0.91 vs skeptic 0.14 — strong bbox overlap, no glare detected",
        media_file: "traffic_crash_zone04.mp4",
        timestamp: t(2),
      },
      {
        id: "inc_001",
        state: "RESPONSE_PROPOSED",
        zone: "Zone 04",
        scenario: "crash_zone04",
        corroborator_score: 0.91,
        skeptic_score: 0.14,
        fused_score: 0.77,
        confidence: 0.9,
        reasoning: "RESPONSE_PROPOSED: awaiting operator clearance to dispatch",
        media_file: "traffic_crash_zone04.mp4",
        timestamp: t(3),
      },
    ];
  }

  return [
    {
      id: "inc_002",
      state: "OBSERVED",
      zone: "Zone 02",
      scenario: "false_alarm",
      corroborator_score: 0.3,
      skeptic_score: 0.25,
      fused_score: 0.05,
      confidence: 0.85,
      reasoning: "OBSERVED: anomaly detected, awaiting agent scoring",
      media_file: "traffic_false_alarm.mp4",
      timestamp: t(0),
    },
    {
      id: "inc_002",
      state: "CANDIDATE",
      zone: "Zone 02",
      scenario: "false_alarm",
      corroborator_score: 0.55,
      skeptic_score: 0.6,
      fused_score: -0.05,
      confidence: 0.85,
      reasoning: "CANDIDATE: initial scoring in progress",
      media_file: "traffic_false_alarm.mp4",
      timestamp: t(1),
    },
    {
      id: "inc_002",
      state: "REJECTED",
      zone: "Zone 02",
      scenario: "false_alarm",
      corroborator_score: 0.58,
      skeptic_score: 0.71,
      fused_score: -0.13,
      confidence: 0.85,
      reasoning:
        "REJECTED: fused score -0.13 below threshold — high glare + camera shake detected, likely lighting anomaly",
      media_file: "traffic_false_alarm.mp4",
      timestamp: t(2),
    },
  ];
}

export const MOCK_SCENARIOS: Record<ScenarioKey, Incident[]> = new Proxy(
  {} as Record<ScenarioKey, Incident[]>,
  {
    get: (_, prop: string) => buildMockScenario(prop as ScenarioKey),
  },
);

export const MOCK_AUDIT_SEED: AuditEntry[] = [
  {
    id: 1,
    timestamp: "2026-09-24T10:15:18Z",
    actor: "system",
    action: "INCIDENT_CREATED: inc_001",
    previous_hash: "0000...0000",
    current_hash: "7b1e...4a2f",
  },
  {
    id: 2,
    timestamp: "2026-09-24T10:15:20Z",
    actor: "safety_governor",
    action: "STATE_TRANSITION: CANDIDATE -> VERIFIED",
    previous_hash: "7b1e...4a2f",
    current_hash: "a3f9...e21c",
  },
  {
    id: 3,
    timestamp: "2026-09-24T10:15:22Z",
    actor: "operator_1",
    action: "APPROVE_DISPATCH: inc_001",
    previous_hash: "a3f9...e21c",
    current_hash: "c88d...910b",
  },
];

const HEX = "0123456789abcdef";
export function shortHash() {
  let out = "";
  for (let i = 0; i < 4; i++) out += HEX[Math.floor(Math.random() * 16)];
  out += "...";
  for (let i = 0; i < 4; i++) out += HEX[Math.floor(Math.random() * 16)];
  return out;
}
