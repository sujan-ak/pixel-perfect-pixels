# AuraShield Demo Script: The 90-Second Judge Walkthrough
### Autonomous Learning with Hindsight Persistent Memory & Asymmetric Safety

---

## The 60-Second Elevator Pitch (For Judges)

> "In emergency dispatch, false alarms cost lives by depleting critical ambulance reserves, while missing a real collision is catastrophic. Current dispatch AI makes the exact same perceptual mistake every single day.
> 
> **AuraShield** solves this using **Hindsight persistent operational memory**. When municipal traffic cameras encounter optical anomalies like sunset glare, operators tag the override. AuraShield retains this context, continuously learning spatial and temporal failure modes. 
> 
> By the third occurrence, our adversarial agents recall historical precedents, dynamically adapt their prior, and autonomously suppress the false alarm—while our **Asymmetric Safety Rule** mathematically guarantees that high-velocity collisions are never silenced. Every decision is cryptographically audited with zero-knowledge tamper verification, keeping the human operator firmly in control."

---

## 90-Second Step-by-Step Live Walkthrough

### Part 1: "The Before" — Memory OFF (0:00 – 0:25)
1. **Show Initial State:**
   - In the **Operator Control Bar**, ensure **MEMORY** switch is **OFF**.
   - Note the grey status LED: `MEMORY OFF`.
2. **Trigger Ambiguous Glare Scenario:**
   - Click the orange **"Simulate: Glare Ambiguous"** button.
   - *Observation:* Video displays low-sun optical flare across Zone 02 at 16:30. Corroborator sees moderate deceleration, Skeptic sees lens flare.
   - *Score:* Pre-memory fused score is $+0.50$ (exceeding $+0.35$).
   - *Result:* Pipeline advances to `RESPONSE_PROPOSED`. Because memory is OFF, the system does not recognize this repeat pattern and halts at the operator barrier.
3. **Operator Override:**
   - Click **"OVERRIDE: REJECT"**.
   - In the modal dialog, select root cause: **Glare / Low Sun** and click **"Confirm Override"**.
   - *Explanation:* *"The human operator clears the false alarm. With Hindsight memory enabled, this feedback is permanently retained to teach the system."*

---

### Part 2: "The After" — Memory ON & Autonomous Suppression (0:25 – 0:50)
1. **Toggle Memory ON:**
   - Switch the **MEMORY** toggle to **ON**.
   - *Observation:* Status LED turns green (`HINDSIGHT CLOUD: ONLINE`) or amber (`LOCAL LEDGER FALLBACK`). Precedent counter displays past incidents.
2. **Trigger "Glare Ambiguous" Again:**
   - Click **"Simulate: Glare Ambiguous"**.
3. **Watch Multi-Agent Learning in Real Time:**
   - **Reasoning Terminal:** Agent `[MEMORY]` appears in vivid purple:
     > *"Recalled 11 precedents for Zone 02 (low-sun optical flare at 16:30). Operator override frequency: 100% false alarm."*
   - **Agent Tug-of-War:** Watch the ghost marker stay at $+0.50$ while the active indicator animates left to **$-0.46$** (delta: $-0.96$).
   - **Badge Display:** The UI highlights: `Suppressed by memory (11 precedents)`.
   - **State Machine:** Automatically transitions to `REJECTED (False Alarm Dismissed)` without wasting operator time!

---

### Part 3: The Learning Curve & Reflective Insights (0:50 – 1:10)
1. **Open the Hindsight Memory Panel:**
   - Point to the **Learning Curve** Recharts chart:
     - *Show the money shot:* Run 1 (+0.50, reaches operator) $\to$ Run 2 (+0.02) $\to$ Run 3 (-0.46, autonomously suppressed).
   - Point to the **Learned Operational Insights** card:
     > *"Zone 02 Camera J2 experiences recurring low-sun optical flare between 15:30 and 17:30 UTC. Suggest polarized optical shielding or sensor recalibration."*
   - Point to the **Recalled Precedents List**: View the exact historical incidents, similarity relevance, and timestamps.

---

### Part 4: The Asymmetric Safety Rule (1:10 – 1:25)
1. **Trigger Real Crash:**
   - Click **"Simulate: Crash Zone 04"**.
2. **Verify That True Collisions Are NEVER Suppressed:**
   - Corroborator scores $+1.0$ (high-velocity physical collision).
   - *Safety Rule in Action:* Because $raw\_corr \ge 0.85$, the memory prior is mathematically forced to $0.0$.
   - *Result:* Pipeline advances to `RESPONSE_PROPOSED`. The human gate is active.
   - Click **"Approve Dispatch"** $\to$ Emergency units dispatched, WhatsApp notifications sent, responder slides mobile ack.
   - *Key Takeaway for Judges:* *"AuraShield gets smarter at filtering noise, but our Asymmetric Safety Rule ensures life-saving emergency dispatches are never blocked by past history."*

---

### Part 5: High Availability & Tamper-Proof Audit (1:25 – 1:30)
1. **Cloud Resilience:**
   - Explain the dual-write circuit breaker: even if cloud connectivity is severed, the local deterministic ledger handles 100% of memory queries with zero latency spike.
2. **Cryptographic Audit:**
   - Point to the green `AUDIT CHAIN: VERIFIED` badge in the header:
     - 1,300+ SHA-256 blocks validated with zero-knowledge cryptographic integrity.

---

## Media & Presentation Shot List

| Shot # | Visual Focus | Caption / Narration |
|:---:|:---|:---|
| **01** | Full Control Room Overview | *AuraShield: Real-time incident adjudication control room with live CCTV feeds and multi-agent reasoning.* |
| **02** | Glare Video + Memory OFF | *Without memory, low-sun optical flare mimics vehicle deceleration, triggering an unnecessary operator intervention.* |
| **03** | Reason Picker Modal | *Operator selects root cause tag `glare`, retaining physical context into Hindsight vector memory.* |
| **04** | Agent Tug-of-War Animation | *With Memory ON, ghost marker shows score flipping from +0.50 to -0.46, autonomously suppressing the false alarm.* |
| **05** | MemoryPanel: Recharts Learning Curve | *The learning curve over runs: quantifiable operational improvement across repeated incidents.* |
| **06** | Asymmetric Safety on Real Crash | *A high-velocity collision is never suppressed: Asymmetric Safety Rule prioritizes life preservation over convenience.* |
| **07** | Cryptographic Ledger & Hash Chain | *Every score adjustment and memory recall is sealed into an immutable SHA-256 audit chain.* |

---

## Emergency Script Backup (Offline / Mock Mode)
If presenting without network access or cloud API keys:
- Leave `VITE_API_URL` unset. The frontend automatically loads `mockData.ts` with offline simulation mode.
- The mock memory simulation replicates the 3-run learning curve, precedent citations, ghost marker tug-of-war shifts, and audit ledger with 100% deterministic fidelity.
