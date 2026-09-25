import asyncio
import logging
import os
from typing import Any, Dict, List, Literal, Optional
from dotenv import load_dotenv

load_dotenv()

from huggingface_hub import InferenceClient
from huggingface_hub.inference._providers import hf_inference

# Ensure the working router endpoint is used for serverless inference
hf_inference.BASE_URL = os.getenv("HF_INFERENCE_ENDPOINT", "https://router.huggingface.co/hf-inference")

logger = logging.getLogger("aurashield.agents.verification")


def get_hf_client() -> InferenceClient:
    return InferenceClient(token=os.getenv("HF_TOKEN"))


# Try these in order — free-tier model availability shifts, so don't 
# hardcode to just one. First one that responds successfully wins.
HF_MODEL_FALLBACK_CHAIN = [
    "HuggingFaceH4/zephyr-7b-beta",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "google/gemma-2-9b-it",
]


async def generate_reasoning(
    state: str,
    scenario: str,
    zone: str,
    corroborator_score: float,
    skeptic_score: float,
    fused_score: float,
    fallback: str,
) -> str:
    prompt = (
        f"You are the reasoning module of a traffic-incident verification "
        f"system. State: {state}. Zone: {zone}. Corroborator agent score: "
        f"{corroborator_score:.2f}. Skeptic agent score: {skeptic_score:.2f}. "
        f"Fused score: {fused_score:.2f}. Write ONE short sentence (under 25 "
        f"words, no markdown, no preamble, no quotation marks) explaining "
        f"this state in the voice of a safety-monitoring system, citing the "
        f"actual numbers and a plausible technical driver (bbox overlap, "
        f"glare, camera shake, motion confidence)."
    )
    client = get_hf_client()
    for model in HF_MODEL_FALLBACK_CHAIN:
        try:
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    client.chat_completion,
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=80,
                ),
                timeout=4.0,
            )
            text = resp.choices[0].message.content.strip()
            if text:
                logger.info("HF model %s generated reasoning: %s", model, text)
                return text
        except Exception as e:
            resp_obj = getattr(e, "response", None)
            status_code = getattr(resp_obj, "status_code", "N/A")
            body = getattr(resp_obj, "text", "") or str(e)
            logger.warning(
                "HF model %s failed: HTTP %s | Error body: %s",
                model,
                status_code,
                body,
            )
            continue
    logger.warning("All HF models failed, using scripted fallback")
    return fallback

from groq import AsyncGroq
import google.generativeai as genai
import json

ScenarioKey = Literal["crash_zone04", "false_alarm"]

SCORING_PROVIDER_CHAIN = ["groq", "gemini", "scripted_fallback"]

TELEMETRY_FIXTURES = {
    "crash_zone04": {
        "zone": "Zone 04",
        "description": (
            "Bounding-box overlap ratio between two vehicles: 0.78 "
            "(sustained across 14 consecutive frames). Frame-to-frame "
            "centroid velocity drop: sharp deceleration detected on both "
            "vehicles simultaneously. Camera glare: none detected. Camera "
            "shake/vibration: minimal, within normal range. Lighting "
            "conditions: stable daylight, no shadow artifacts."
        ),
    },
    "false_alarm": {
        "zone": "Zone 02",
        "description": (
            "Bounding-box overlap ratio: 0.31, persisted for only 2 "
            "frames before resolving. No sustained deceleration pattern "
            "detected. Camera glare: significant lens flare detected "
            "consistent with direct sunlight angle. Camera shake: "
            "elevated vibration signature, consistent with wind or "
            "mounting instability. A shadow artifact crosses the frame "
            "during the flagged window."
        ),
    },
}

CORROBORATOR_SYSTEM = (
    "You are the Corroborator agent in a traffic-incident verification system. "
    "Your objective is to evaluate whether the telemetry indicates a real vehicular collision. "
    "Examine the telemetry carefully: "
    "- If telemetry shows high bounding-box overlap sustained over 10+ frames with sharp deceleration, collision probability is high: score MUST be high (0.85 to 0.98). "
    "- If telemetry shows brief overlap (1-3 frames), no deceleration, or transient anomaly, collision probability is low: score MUST be low (0.15 to 0.40). "
    "Respond with strict JSON only: "
    '{"score": <float 0.0-1.0 representing collision probability>, "confidence": <float 0.0-1.0>, "evidence": [<at least 2 strings citing specific telemetry factors>]}'
)
SKEPTIC_SYSTEM = (
    "You are the Skeptic agent in a traffic-incident verification system. "
    "Your objective is to evaluate whether the telemetry indicates a false alarm (optical glare, camera vibration, shadow artifact, or momentary occlusion). "
    "Examine the telemetry carefully: "
    "- If telemetry shows sustained high bounding-box overlap over 10+ frames with zero glare and zero vibration, honest assessment shows minimal false positive evidence: score MUST be low (0.05 to 0.25). "
    "- If telemetry shows lens flare, camera shake, short persistence (1-3 frames), or shadow artifacts, false alarm probability is high: score MUST be high (0.70 to 0.92). "
    "Respond with strict JSON only: "
    '{"score": <float 0.0-1.0 representing false-alarm/noise probability>, "confidence": <float 0.0-1.0>, "evidence": [<at least 2 strings citing specific telemetry factors>]}'
)


def get_groq_client() -> AsyncGroq:
    return AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))


async def call_groq_agent(system_prompt: str, telemetry_description: str) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError("GROQ_API_KEY is not set")
    client = get_groq_client()
    preferred_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    models_to_try = [preferred_model, "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

    last_err: Optional[Exception] = None
    for model in models_to_try:
        try:
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Telemetry: {telemetry_description}"},
                    ],
                ),
                timeout=6.0,
            )
            raw = resp.choices[0].message.content
            return json.loads(raw)
        except Exception as e:
            last_err = e
            # If model not found, try next candidate
            if "model_not_found" in str(e) or "does not exist" in str(e):
                continue
            raise e
    if last_err:
        raise last_err
    raise RuntimeError("All Groq model attempts exhausted")


async def call_gemini_agent(system_prompt: str, telemetry_description: str) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError("GEMINI_API_KEY is not set")

    genai.configure(api_key=api_key)
    preferred_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    models_to_try = [preferred_model, "gemini-2.0-flash", "gemini-2.5-flash"]

    full_prompt = (
        f"{system_prompt}\n\n"
        f"Telemetry:\n{telemetry_description}\n\n"
        f"Respond with strict JSON matching the requested schema."
    )

    def _sync_gemini_call(model_name: str) -> str:
        model = genai.GenerativeModel(model_name)
        res = model.generate_content(
            full_prompt,
            generation_config={"response_mime_type": "application/json", "temperature": 0.2},
        )
        return res.text

    last_err: Optional[Exception] = None
    for model_name in models_to_try:
        try:
            text = await asyncio.wait_for(
                asyncio.to_thread(_sync_gemini_call, model_name),
                timeout=6.0,
            )
            return json.loads(text)
        except Exception as e:
            last_err = e
            if "NOT_FOUND" in str(e) or "404" in str(e):
                continue
            raise e
    if last_err:
        raise last_err
    raise RuntimeError("All Gemini model attempts exhausted")


async def call_single_agent_with_fallback(
    agent_name: str,
    system_prompt: str,
    telemetry_description: str,
    fallback_score: float,
    fallback_evidence: List[str],
) -> tuple[dict, str]:
    """
    Executes SCORING_PROVIDER_CHAIN: Groq -> Gemini -> Scripted Fallback.
    Returns (result_dict, provider_name).
    """
    for provider in SCORING_PROVIDER_CHAIN:
        if provider == "groq":
            try:
                res = await call_groq_agent(system_prompt, telemetry_description)
                if "score" in res and "evidence" in res:
                    logger.info("[SCORING PROVIDER] Agent '%s' successfully served by Groq", agent_name)
                    return res, "groq"
            except Exception as e:
                logger.warning("[SCORING PROVIDER] Groq failed for '%s' (fallback to Gemini): %s", agent_name, e)
                continue

        elif provider == "gemini":
            try:
                res = await call_gemini_agent(system_prompt, telemetry_description)
                if "score" in res and "evidence" in res:
                    logger.info("[SCORING PROVIDER] Agent '%s' successfully served by Gemini", agent_name)
                    return res, "gemini"
            except Exception as e:
                logger.warning("[SCORING PROVIDER] Gemini failed for '%s' (fallback to scripted): %s", agent_name, e)
                continue

        elif provider == "scripted_fallback":
            logger.warning("[SCORING PROVIDER] Agent '%s' falling back to scripted heuristic scores", agent_name)
            return {
                "score": fallback_score,
                "confidence": 0.90,
                "evidence": fallback_evidence,
            }, "scripted_fallback"

    return {
        "score": fallback_score,
        "confidence": 0.90,
        "evidence": fallback_evidence,
    }, "scripted_fallback"


async def get_real_scores(
    scenario: str, fallback_corr: float, fallback_skep: float
) -> tuple[float, float, float, bool, List[str], List[str], str]:
    """
    Returns (corroborator_score, skeptic_score, confidence, degraded, corr_evidence, skep_evidence, provider_summary)
    """
    fixture = TELEMETRY_FIXTURES.get(scenario)
    if not fixture:
        return (
            fallback_corr,
            fallback_skep,
            0.90,
            True,
            ["Scripted fallback: unknown scenario fixture"],
            ["Scripted fallback: unknown scenario fixture"],
            "scripted_fallback",
        )

    telemetry_desc = fixture["description"]
    fallback_corr_ev = (
        ["High vehicle bbox overlap (0.78) sustained over 14 frames", "Sharp decelerations on both trajectories"]
        if scenario == "crash_zone04"
        else ["Brief bbox overlap (0.31) resolved in 2 frames", "Minor speed variation"]
    )
    fallback_skep_ev = (
        ["Minimal camera shake, daylight clarity rules out noise", "Sustained deceleration confirms physical contact"]
        if scenario == "crash_zone04"
        else ["High lens flare consistent with direct sunlight angle", "Wind vibration signature detected on mount"]
    )

    (corr_resp, corr_prov), (skep_resp, skep_prov) = await asyncio.gather(
        call_single_agent_with_fallback(
            "CORROBORATOR", CORROBORATOR_SYSTEM, telemetry_desc, fallback_corr, fallback_corr_ev
        ),
        call_single_agent_with_fallback(
            "SKEPTIC", SKEPTIC_SYSTEM, telemetry_desc, fallback_skep, fallback_skep_ev
        ),
    )

    provider_summary = f"{corr_prov}+{skep_prov}"
    degraded = (corr_prov == "scripted_fallback" or skep_prov == "scripted_fallback")

    try:
        corr_score = float(corr_resp.get("score", fallback_corr))
        skep_score = float(skep_resp.get("score", fallback_skep))
        corr_conf = float(corr_resp.get("confidence", 0.9))
        skep_conf = float(skep_resp.get("confidence", 0.9))
        # Weight confidence toward whichever agent scored higher (dominant hypothesis)
        if corr_score >= skep_score:
            confidence = round(0.70 * corr_conf + 0.30 * skep_conf, 2)
        else:
            confidence = round(0.30 * corr_conf + 0.70 * skep_conf, 2)
        corr_evidence = corr_resp.get("evidence", fallback_corr_ev)
        skep_evidence = skep_resp.get("evidence", fallback_skep_ev)
        return (
            corr_score,
            skep_score,
            float(confidence),
            degraded,
            corr_evidence,
            skep_evidence,
            provider_summary,
        )
    except Exception as e:
        logger.warning("Error parsing scores from provider results (%s): %s", provider_summary, e)
        return (
            fallback_corr,
            fallback_skep,
            0.90,
            True,
            fallback_corr_ev,
            fallback_skep_ev,
            "scripted_fallback",
        )


def compute_fused_score(corroborator_score: float, skeptic_score: float) -> float:
    return round(corroborator_score - skeptic_score, 2)



def evaluate_scores(
    corroborator_score: float,
    skeptic_score: float,
    confidence: Optional[float] = None,
    threshold: float = 0.65,
) -> str:
    """
    Evaluator fusion logic:
      fused = corroborator - skeptic
      VERIFIED if fused > 0.35 AND confidence >= threshold (default 0.65)
      else falls through toward REJECTED
    """
    fused = compute_fused_score(corroborator_score, skeptic_score)
    conf = confidence if confidence is not None else 0.90
    if fused > 0.35 and conf >= threshold:
        return "VERIFIED"
    return "REJECTED"


def assert_terminal_state_matches(
    fixture_state: str,
    corroborator_score: float,
    skeptic_score: float,
    confidence: Optional[float] = None,
    threshold: float = 0.65,
) -> None:
    """
    Self-check assertion run on the final step of a scenario.
    Logs a warning if the fixture state differs from the formula result.
    Does not raise or alter the fixture state.
    """
    computed = evaluate_scores(corroborator_score, skeptic_score, confidence, threshold=threshold)
    expected = "VERIFIED" if fixture_state in ("VERIFIED", "RESPONSE_PROPOSED") else "REJECTED"
    if computed != expected:
        logger.warning(
            "Terminal evaluation self-check mismatch: fixture says '%s' (expected %s), formula evaluated '%s' "
            "(corroborator=%.2f, skeptic=%.2f, fused=%.2f, confidence=%s)",
            fixture_state,
            expected,
            computed,
            corroborator_score,
            skeptic_score,
            compute_fused_score(corroborator_score, skeptic_score),
            f"{confidence:.2f}" if confidence is not None else "N/A",
        )
    else:
        logger.info(
            "Terminal evaluation self-check verified: state='%s' matches formula '%s' "
            "(corroborator=%.2f, skeptic=%.2f, fused=%.2f)",
            fixture_state,
            computed,
            corroborator_score,
            skeptic_score,
            compute_fused_score(corroborator_score, skeptic_score),
        )


SCENARIO_FIXTURES: Dict[str, Dict[str, Any]] = {
    "crash_zone04": {
        "zone": "Zone 04",
        "media_file": "traffic_crash_zone04.mp4",
        "steps": [
            {
                "state": "OBSERVED",
                "corroborator_score": 0.20,
                "skeptic_score": 0.10,
                "fused_score": 0.10,
                "reasoning": "OBSERVED: anomaly detected, awaiting agent scoring",
            },
            {
                "state": "CANDIDATE",
                "corroborator_score": 0.65,
                "skeptic_score": 0.20,
                "fused_score": 0.45,
                "reasoning": "CANDIDATE: initial scoring in progress",
            },
            {
                "state": "VERIFIED",
                "corroborator_score": 0.91,
                "skeptic_score": 0.14,
                "fused_score": 0.77,
                "reasoning": (
                    "VERIFIED: fused score 0.77, corroborator 0.91 vs skeptic 0.14 "
                    "— strong bbox overlap, no glare detected"
                ),
            },
            {
                "state": "RESPONSE_PROPOSED",
                "corroborator_score": 0.91,
                "skeptic_score": 0.14,
                "fused_score": 0.77,
                "reasoning": "RESPONSE_PROPOSED: awaiting operator clearance to dispatch",
            },
        ],
    },
    "false_alarm": {
        "zone": "Zone 02",
        "media_file": "traffic_false_alarm.mp4",
        "steps": [
            {
                "state": "OBSERVED",
                "corroborator_score": 0.30,
                "skeptic_score": 0.25,
                "fused_score": 0.05,
                "reasoning": "OBSERVED: anomaly detected, awaiting agent scoring",
            },
            {
                "state": "CANDIDATE",
                "corroborator_score": 0.55,
                "skeptic_score": 0.60,
                "fused_score": -0.05,
                "reasoning": "CANDIDATE: initial scoring in progress",
            },
            {
                "state": "REJECTED",
                "corroborator_score": 0.58,
                "skeptic_score": 0.71,
                "fused_score": -0.13,
                "reasoning": (
                    "REJECTED: fused score -0.13 below threshold — high glare + "
                    "camera shake detected, likely lighting anomaly"
                ),
            },
        ],
    },
}
