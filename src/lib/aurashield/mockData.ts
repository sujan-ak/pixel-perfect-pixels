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

  if (scenario === "glare_ambiguous") {
    const memoryObj = {
      enabled: true,
      used: true,
      source: "local-fallback",
      precedents: [
        {
          text: "Operator Ravi confirmed false positive: momentary glare occlusion during 17:00 sunset angle. No vehicle contact.",
          source: "local-fallback" as const,
          relevance: 0.94,
          zone: "Zone 02",
          cause_tags: ["glare", "optical_flare"],
        },
        {
          text: "Operator Priya overrode candidate: direct solar flare reflecting off Cyber Towers glass façade onto traffic lane.",
          source: "local-fallback" as const,
          relevance: 0.91,
          zone: "Zone 02",
          cause_tags: ["glare", "lens_flare"],
        },
        {
          text: "Operator Ravi noted severe low-sun glare from west-facing lens at Hitec City junction; bbox overlap 0.32 resolved in 2 frames.",
          source: "local-fallback" as const,
          relevance: 0.88,
          zone: "Zone 02",
          cause_tags: ["glare", "lens_flare"],
        },
      ],
      adjustment: {
        applied: true,
        corr_delta: -0.12,
        skep_delta: 0.25,
        delta: 0.25,
        dominant: "false_alarm",
        dominant_count: 8,
        reason:
          "Memory prior: 8 operator-confirmed false alarms dominate (100%); skeptic boosted +0.25",
      },
      pre_memory_scores: {
        corr: 0.68,
        skep: 0.22,
        fused: 0.46,
      },
      post_memory_scores: {
        corr: 0.56,
        skep: 0.47,
        fused: 0.09,
      },
      suppressed_by_memory: true,
    };

    return [
      {
        id: "inc_003",
        state: "OBSERVED",
        zone: "Zone 02",
        scenario: "glare_ambiguous",
        corroborator_score: 0.35,
        skeptic_score: 0.15,
        fused_score: 0.2,
        confidence: 0.88,
        reasoning: "OBSERVED: anomaly detected, awaiting agent scoring",
        media_file: "traffic_false_alarm.mp4",
        timestamp: t(0),
        memory: memoryObj,
      },
      {
        id: "inc_003",
        state: "CANDIDATE",
        zone: "Zone 02",
        scenario: "glare_ambiguous",
        corroborator_score: 0.58,
        skeptic_score: 0.18,
        fused_score: 0.4,
        confidence: 0.88,
        reasoning: "CANDIDATE: initial scoring in progress",
        media_file: "traffic_false_alarm.mp4",
        timestamp: t(1),
        memory: memoryObj,
      },
      {
        id: "inc_003",
        state: "REJECTED",
        zone: "Zone 02",
        scenario: "glare_ambiguous",
        corroborator_score: 0.56,
        skeptic_score: 0.47,
        fused_score: 0.09,
        confidence: 0.88,
        reasoning:
          "Suppressed by memory (8 precedents) — Memory prior: 8 operator-confirmed false alarms dominate (100%); skeptic boosted +0.25",
        media_file: "traffic_false_alarm.mp4",
        timestamp: t(2),
        memory: memoryObj,
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

export const MOCK_MEMORY_STATUS = {
  enabled: true,
  hindsight_reachable: true,
  bank_id: "aurashield-ops",
  events_in_ledger: 28,
  last_error: null,
  circuit_breaker_open: false,
};

export const MOCK_MEMORY_INSIGHTS = {
  insights:
    "AuraShield Operational Insights (Synthesized from 28 ledger events):\n" +
    "- Zone 02 Recurring Glare: 8 operator-confirmed false alarms between 15:30-17:30 IST due to west-facing low-sun lens flare at Hitec City junction.\n" +
    "- Zone 04 Critical Corridor: 6 confirmed multi-vehicle collisions requiring emergency response; avg dispatch clearance 8.2s.\n" +
    "- Peak-Hour Hospital Routing: Hospital H_ALPHA experienced 4 peak-hour transfer declines; emergency green corridor actively reroutes to H_BETA during 17:00-19:30 window.",
  cached: true,
  timestamp: "2026-09-29T12:00:00Z",
};

export const MOCK_LEARNING_CURVE = [
  {
    run: 1,
    scenario: "glare_ambiguous",
    pre_memory_fused: 0.44,
    post_memory_fused: 0.44,
    verdict: "REJECTED",
    precedents: 0,
  },
  {
    run: 2,
    scenario: "glare_ambiguous",
    pre_memory_fused: 0.45,
    post_memory_fused: 0.38,
    verdict: "REJECTED",
    precedents: 1,
  },
  {
    run: 3,
    scenario: "crash_zone04",
    pre_memory_fused: 0.77,
    post_memory_fused: 0.77,
    verdict: "VERIFIED",
    precedents: 2,
  },
  {
    run: 4,
    scenario: "glare_ambiguous",
    pre_memory_fused: 0.46,
    post_memory_fused: 0.28,
    verdict: "REJECTED",
    precedents: 3,
  },
  {
    run: 5,
    scenario: "crash_zone04",
    pre_memory_fused: 0.79,
    post_memory_fused: 0.79,
    verdict: "VERIFIED",
    precedents: 4,
  },
  {
    run: 6,
    scenario: "glare_ambiguous",
    pre_memory_fused: 0.46,
    post_memory_fused: 0.16,
    verdict: "REJECTED",
    precedents: 5,
  },
  {
    run: 7,
    scenario: "crash_zone04",
    pre_memory_fused: 0.81,
    post_memory_fused: 0.81,
    verdict: "VERIFIED",
    precedents: 6,
  },
  {
    run: 8,
    scenario: "glare_ambiguous",
    pre_memory_fused: 0.46,
    post_memory_fused: 0.09,
    verdict: "REJECTED",
    precedents: 8,
  },
];

export const MOCK_MEMORY_TIMELINE = [
  {
    event_id: "seed_z02_glare_08",
    ts: "2026-09-28T16:50:00Z",
    kind: "OPERATOR_OVERRIDE",
    incident_id: "INC-HYD-0925-07",
    zone: "Zone 02",
    scenario: "glare_ambiguous",
    cause_tags: ["glare", "lens_flare"],
    operator_action: "OVERRIDE_REJECT",
    outcome: "REJECTED",
    corr_score: 0.47,
    skeptic_score: 0.58,
    fused_score: -0.11,
    notes:
      "Operator Vikram confirmed low-sun optical flare at Madhapur flyover junction; candidate rejected.",
  },
  {
    event_id: "seed_z04_crash_06",
    ts: "2026-09-27T18:15:00Z",
    kind: "OPERATOR_APPROVED",
    incident_id: "INC-HYD-0924-03",
    zone: "Zone 04",
    scenario: "crash_zone04",
    cause_tags: ["collision", "multi_vehicle"],
    operator_action: "APPROVE_DISPATCH",
    outcome: "DISPATCHED",
    corr_score: 0.93,
    skeptic_score: 0.12,
    fused_score: 0.81,
    notes:
      "Operator Ravi verified high-severity rear-end collision; immediate ambulance green corridor dispatched.",
  },
  {
    event_id: "seed_hosp_decline_03",
    ts: "2026-09-26T18:45:00Z",
    kind: "DISPATCH_DECLINED",
    incident_id: "INC-HYD-0922-08",
    zone: "Zone 04",
    scenario: "crash_zone04",
    hospital_id: "H_ALPHA",
    notes: "H_ALPHA ER bay saturated during evening peak rush; replanned dispatch to H_BETA.",
  },
];

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
