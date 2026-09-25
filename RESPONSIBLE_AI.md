# Responsible AI & Safety Governance Framework
**System:** AuraShield Municipal Safety Incident Orchestrator  
**Version:** 1.0.0 (Production Adjudication Engine)  
**Standard:** ISO/IEC 42001 (Artificial Intelligence Management System) & NIST AI RMF 1.0  

---

## 1. Human-in-the-Loop (HITL) by Design

AuraShield operates under an unconditional **Non-Autonomous Actuation Policy**:
> **Core Invariant:** *No emergency dispatch, physical siren activation, or municipal traffic pre-emption signal can EVER be transmitted solely by autonomous AI inference.*

### Code-Level Guarantee
The orchestration state machine enforces a hard execution barrier at the `RESPONSE_PROPOSED` phase.
In [`backend/core/state_machine.py`](file:///c:/Users/sujan/Downloads/pixel-perfect-pixels-main/backend/core/state_machine.py) (Lines 317–336):

```python
# HARD SAFETY BARRIER: The autonomous pipeline deliberately halts here.
# Under no circumstances will automated dispatch proceed without an explicit
# operator POST to /incidents/{incident_id}/approve.
logger.info(
    "Incident %s entered RESPONSE_PROPOSED. Gating on authenticated human clearance.",
    incident.id,
)
```

1. **Mandatory Human Clearance:** Even if both Corroborator and Skeptic agents output maximum collision confidence ($1.0$), the system strictly transitions to `RESPONSE_PROPOSED` and **pauses execution**.
2. **Authenticated Operator Action:** Only an authenticated human operator clicking **"Approve Dispatch"** or **"Override: Reject"** can cause a state transition to `DISPATCH_APPROVED` or `REJECTED`.
3. **Operator Override Veto:** At any point during live streaming adjudication or proposed response, the human operator can trigger `POST /incidents/{id}/override-reject`, instantly terminating agent workflows and writing an immutable `OPERATOR_OVERRIDE_REJECT` block to the cryptographic ledger.
4. **Pause Automation:** Operators can engage `AUTOMATION PAUSED` mode at any moment, freezing all pipeline activations across city sectors.

---

## 2. Adversarial Verification as Harm Reduction

In emergency response, a **false positive dispatch** is not merely an inconvenience—it actively deprives someone else of life-saving medical care. Dispatching an Advanced Life Support (ALS) ambulance to a harmless near-miss or blown garbage bag depletes municipal emergency reserves.

To combat bias toward premature action, AuraShield uses an **Adversarial Dual-Agent Architecture**:

```mermaid
flowchart LR
    A[Telemetry & Sensor Feed] --> B[Corroborator Agent]
    A --> C[Skeptic Agent]
    B -->|Collision Likelihood S_c| D[Safety Governor]
    C -->|Benign Explanation S_s| D
    D -->|Fused Score > 0.35 AND Conf >= Threshold| E[RESPONSE_PROPOSED (Human Gate)]
    D -->|Fused Score <= 0.35 OR Conf < Threshold| F[REJECTED (False Alarm Dismissed)]
```

- **The Corroborator Agent** is prompted as a safety advocate: searching for physical evidence of collision (IoU overlap spikes, rapid deceleration, pedestrian proximity).
- **The Skeptic Agent** is actively incentivized to uncover benign explanations: near-misses with evasive steering, shadows, parallax occlusions, or camera vibration.
- **The Safety Governor** mathematically fuses their claims:
  $$\text{Fused Score} = S_{\text{corroborator}} - S_{\text{skeptic}}$$
  Gated strictly on:
  $$\text{Fused Score} > 0.35 \quad \land \quad \text{Confidence} \ge \tau_{\text{governor}}$$
  (Where $\tau_{\text{governor}}$ defaults to $0.80$, adjustable between $0.50$ and $0.95$ via real-time operator control).

---

## 3. Cryptographic Auditability & Chain of Custody

Every single action in the AuraShield platform is mathematically immutable:
- Every scenario trigger, camera perception snapshot, agent inference chunk, fused decision score, and operator veto is hashed and committed to an append-only ledger.
- **Cryptographic Chaining:** Each block $B_i$ contains:
  $$H_i = \text{SHA-256}(H_{i-1} \mathbin{\Vert} \text{Actor} \mathbin{\Vert} \text{Action} \mathbin{\Vert} \text{Timestamp})$$
  Genesis block starts at $H_0 = \text{"0"}^{64}$.
- **Zero-Knowledge Tamper Detection:** The `/audit/verify` endpoint verifies the mathematical validity of the complete cryptographic hash chain. Any direct database row modification or deleted record breaks the downstream hash chain instantly, displaying an amber tamper alert in the operator console.
- **Operator Attribution:** All human overrides record the operator's verified identifier (`operator_1`), timestamp, and explicit rationale directly in the ledger.

---

## 4. Privacy by Design & Zero Identity Inference

AuraShield is built strictly for **physical physics validation**, not individual surveillance:
1. **No Facial Recognition:** No face detection, facial embeddings, or biometric recognition models exist in the pipeline.
2. **No License Plate Tracking (ALPR):** Video feeds are processed strictly for bounding-box coordinates, spatial IoU overlap, and optical-flow velocity vectors. License plates are neither extracted nor stored.
3. **Detection Class Whitelist:** Perception models are strictly constrained to coarse generic classes: `["car", "truck", "bus", "motorcycle", "person"]`.
4. **Ephemeral Frame Retention:** Raw video frames and sensor buffers are processed in volatile RAM and immediately discarded following agent adjudication. Only metadata, bounding box coordinates, and cryptographic hashes are persisted.

---

## 5. Known Bias & Infrastructure Equity

Autonomous incident systems inherit the biases of physical urban infrastructure:
- **Surveillance Density Disparity:** High-income arterial roads and commercial city centres possess high-resolution 4K CCTV coverage and optical sensors. Low-income or peri-urban neighbourhoods typically feature lower camera density, poorer lighting, or zero sensor coverage.
- **Equity Hazard:** A system that only responds to automated camera detections risks prioritizing well-funded municipal districts over under-resourced communities.
- **Mitigation Strategy:** AuraShield provides multi-modal ingest paths: supporting low-bandwidth emergency SMS reports, community acoustic sensors, and manual 112/911 operator triage injections to ensure equal emergency access regardless of localized camera infrastructure.

---

## 6. Stated Failure Modes & Graceful Degradation

Safety-critical systems must acknowledge and handle edge failures transparently:

| Failure Mode | Physical Cause | AuraShield Mitigation |
| :--- | :--- | :--- |
| **Optical Occlusion** | Heavy monsoon rain, headlight glare, night darkness | Optical flow confidence score drops below baseline; system flags incident as `degraded=True` and falls back to acoustic/telemetry corroboration. |
| **Acoustic Noise** | Loud construction, thunder, festive fireworks | Acoustic trigger requires spatial camera validation before triggering high-priority adjudication. |
| **Primary LLM Timeout** | API rate limit or upstream cloud provider outage | Multi-tier provider chain automatically cascades: **Groq** (6s) $\to$ **Gemini** (6s) $\to$ **Deterministic Scripted Safety Fallback**, flagging the state machine as degraded. |
| **Network Partition** | Edge camera loses WAN connection to cloud | Edge node queues telemetry locally and caches cryptographic ledger entries for replay synchronization upon reconnect. |
