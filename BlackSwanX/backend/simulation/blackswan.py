"""BlackSwan Module — The "What-If" injector that stress-tests predictions.

Injects unlikely but high-impact variables into a completed simulation
to see how robust the predictions are.

Think: "What if the CEO resigns tomorrow?" or "What if a major leak drops?"
"""
import json
from backend.llm.router import smart_chat

BLACKSWAN_SYSTEM = """You are the BlackSwan Module — a chaos engineer for predictions.

Given a prediction and its context, you inject UNLIKELY BUT HIGH-IMPACT events
(Black Swans) to stress-test the prediction's robustness.

For each Black Swan:
1. Describe the event (specific, not vague)
2. Estimate its probability (should be LOW, <20%)
3. Estimate its impact IF it happens (should be HIGH)
4. Show how the prediction changes under this scenario

Output JSON:
{
  "black_swans": [
    {
      "event": "specific description",
      "probability": 0.0-0.2,
      "impact_score": 0.0-1.0,
      "prediction_change": "how the main prediction shifts",
      "cascade_effects": ["effect 1", "effect 2"]
    }
  ],
  "robustness_score": 0.0-1.0,
  "most_dangerous_swan": "the one Black Swan that would cause maximum damage",
  "recommendation": "how the decision-maker should hedge"
}"""


async def inject_black_swans(
    prediction_context: str,
    num_swans: int = 3,
) -> dict:
    """Generate Black Swan scenarios to stress-test a prediction."""
    prompt = f"""PREDICTION TO STRESS-TEST:
{prediction_context}

Generate {num_swans} Black Swan events that could shatter this prediction.
Each must be specific, unlikely (<20% probability), but devastating if it occurs."""

    response, model = await smart_chat(
        prompt=prompt,
        system=BLACKSWAN_SYSTEM,
        json_mode=True,
        force_model="assassin",  # phi4:14b — deep reasoning for kill shots
    )

    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        result = {
            "black_swans": [],
            "robustness_score": 0.5,
            "raw_response": response,
        }

    result["model_used"] = model
    return result


async def what_if(
    prediction_context: str,
    user_scenario: str,
) -> dict:
    """User-injected 'What-If' scenario.

    The user asks: "What if X happens?" and we re-evaluate the prediction.
    """
    prompt = f"""CURRENT PREDICTION:
{prediction_context}

USER INJECTS THIS SCENARIO:
"{user_scenario}"

Re-evaluate the entire prediction assuming this event DEFINITELY HAPPENS.
How does everything change?

Output JSON:
{{
  "original_outcome": "what was predicted before",
  "new_outcome": "what happens with this injection",
  "confidence_shift": "how much confidence changes",
  "cascade_effects": ["..."],
  "new_pressure_points": ["..."],
  "verdict": "one sentence on whether this changes everything or is absorbable"
}}"""

    response, model = await smart_chat(
        prompt=prompt,
        system="You are a scenario analyst. Re-evaluate predictions when new variables are injected.",
        json_mode=True,
        force_model="assassin",  # phi4:14b — deep reasoning for kill shots
    )

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"verdict": response}
