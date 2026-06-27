"""Narrative Kill-Switch — The feature that makes this go viral.

Runs a digital "War Room":
- Swarm A (The Fans): Builds a "Hype Report" defending the trend
- Swarm B (The Assassins): Finds the single most damaging info to tank the trend
- Stress-Test: Fans defend, Assassins attack
- Output: Volatility Score, not just a report

Example: "Hype is 80%, but Kill-Switch shows 90% collapse risk if [Variable X] happens."
"""
import json
from backend.llm.router import smart_chat
from backend.llm.prompts import PROVOCATEUR_SYSTEM, WHALE_SYSTEM

FANS_SYSTEM = """You are Swarm A — The Fans. Your job is to build the STRONGEST possible case
for why this trend/event will SUCCEED and GROW.

Be specific: cite evidence, momentum, tailwinds, supporter base.
You are a hype machine with data backing.

Output JSON:
{
  "hype_score": 0.0-1.0,
  "bull_case": "strongest argument for success",
  "evidence": ["point 1", "point 2", "point 3"],
  "momentum_indicators": ["..."],
  "tailwinds": ["..."]
}"""

ASSASSINS_SYSTEM = """You are Swarm B — The Assassins. Your ONLY job is to find the single most
DAMAGING piece of information that could TANK this trend completely.

Think like a short seller, investigative journalist, or hostile adversary.
Find the kill shot — the one thing that makes everything collapse.

Output JSON:
{
  "kill_shot": "the single most damaging revelation or event",
  "collapse_probability": 0.0-1.0,
  "attack_vectors": [{"vector": "...", "damage_potential": 0.0-1.0}],
  "weakest_link": "the thing everyone is ignoring",
  "timeline_to_collapse": "if triggered, how fast does it fall"
}"""


async def run_kill_switch(topic: str, personas_context: str) -> dict:
    """Run the Narrative Kill-Switch stress test.

    Returns a Volatility Score with detailed breakdown.
    """
    context = f"Topic: {topic}\n\nSocial Persona Context:\n{personas_context}"

    # Run Fans and Assassins in parallel conceptually (sequential for Ollama)
    fans_response, _ = await smart_chat(
        prompt=f"{context}\n\nBuild the strongest hype case.",
        system=FANS_SYSTEM,
        json_mode=True,
        force_model="assassin",  # phi4:14b for kill-switch analysis
    )

    assassins_response, _ = await smart_chat(
        prompt=f"{context}\n\nFind the kill shot.",
        system=ASSASSINS_SYSTEM,
        json_mode=True,
        force_model="assassin",  # phi4:14b for kill-switch analysis
    )

    # Parse responses
    try:
        fans_data = json.loads(fans_response)
    except json.JSONDecodeError:
        fans_data = {"hype_score": 0.5, "bull_case": fans_response}

    try:
        assassins_data = json.loads(assassins_response)
    except json.JSONDecodeError:
        assassins_data = {"collapse_probability": 0.5, "kill_shot": assassins_response}

    # Run the War Room — Fans defend against the kill shot
    war_room_prompt = f"""WAR ROOM STRESS TEST

The Fans say: {fans_data.get('bull_case', 'N/A')}
Hype Score: {fans_data.get('hype_score', 'N/A')}

The Assassins found this Kill Shot: {assassins_data.get('kill_shot', 'N/A')}
Collapse Probability: {assassins_data.get('collapse_probability', 'N/A')}

Now, as a neutral judge, score the VOLATILITY:
- Can the Fans' hype survive the Kill Shot?
- What is the real risk?

Output JSON:
{{
  "volatility_score": 0.0-1.0,
  "hype_survives": true/false,
  "adjusted_collapse_risk": 0.0-1.0,
  "verdict": "one sentence final verdict",
  "critical_variable": "the single variable that determines the outcome"
}}"""

    verdict_response, _ = await smart_chat(
        prompt=war_room_prompt,
        system="You are a neutral War Room judge evaluating competing intelligence reports.",
        json_mode=True,
        force_model="assassin",  # phi4:14b for kill-switch analysis
    )

    try:
        verdict = json.loads(verdict_response)
    except json.JSONDecodeError:
        verdict = {"volatility_score": 0.5, "verdict": verdict_response}

    return {
        "fans": fans_data,
        "assassins": assassins_data,
        "verdict": verdict,
        "volatility_score": verdict.get("volatility_score", 0.5),
    }
