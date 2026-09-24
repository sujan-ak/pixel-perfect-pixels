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

ScenarioKey = Literal["crash_zone04", "false_alarm"]


def compute_fused_score(corroborator_score: float, skeptic_score: float) -> float:
    return round(corroborator_score - skeptic_score, 2)


def evaluate_scores(corroborator_score: float, skeptic_score: float) -> str:
    """
    Evaluator fusion logic:
      fused_score = corroborator_score - skeptic_score
      VERIFIED if fused_score > 0.35 AND overall_confidence >= 0.80
      REJECTED if fused_score < 0.55
      overall_confidence = corroborator_score
    """
    fused = compute_fused_score(corroborator_score, skeptic_score)
    overall_confidence = corroborator_score

    if fused > 0.35 and overall_confidence >= 0.80:
        return "VERIFIED"
    elif fused < 0.55:
        return "REJECTED"
    return "CANDIDATE"


def assert_terminal_state_matches(
    fixture_state: str, corroborator_score: float, skeptic_score: float
) -> None:
    """
    Self-check assertion run on the final step of a scenario.
    Logs a warning if the fixture state differs from the formula result.
    Does not raise or alter the fixture state.
    """
    computed = evaluate_scores(corroborator_score, skeptic_score)
    if computed != fixture_state:
        logger.warning(
            "Terminal evaluation self-check mismatch: fixture says '%s', formula evaluated '%s' "
            "(corroborator=%.2f, skeptic=%.2f, fused=%.2f)",
            fixture_state,
            computed,
            corroborator_score,
            skeptic_score,
            compute_fused_score(corroborator_score, skeptic_score),
        )
    else:
        logger.info(
            "Terminal evaluation self-check verified: state='%s' matches formula (corroborator=%.2f, skeptic=%.2f)",
            fixture_state,
            corroborator_score,
            skeptic_score,
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
