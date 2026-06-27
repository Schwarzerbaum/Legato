"""Elite Panel — Domain experts analyze the swarm and defend against the Kill Shot.

The Elites don't just analyze in isolation. They receive:
1. The Social Personas (compressed vibes)
2. The BlackSwan's Kill Shot (must defend or confirm)
3. The Swarm Census (what the masses think)

Their job: Expert analysis WITH adversarial pressure.
"""
import json
from backend.llm.router import smart_chat
from backend.llm.prompts import ELITE_REGISTRY, TOPIC_ROUTER_SYSTEM


async def select_relevant_elites(topic: str) -> list[str]:
    """Use LLM to auto-select which domain experts are relevant for this topic."""
    response, _ = await smart_chat(
        prompt=f"Topic: {topic}",
        system=TOPIC_ROUTER_SYSTEM,
        json_mode=True,
        force_model="swarm",  # Cheap model for routing
    )

    try:
        data = json.loads(response)
        return data.get("active_elites", ["provocateur", "whale", "catalyst"])
    except json.JSONDecodeError:
        return ["provocateur", "whale", "catalyst"]


async def run_elite_panel(
    topic: str,
    vibes: list,
    kill_shot: dict,
    swarm_summary: dict,
) -> dict:
    """Run all relevant elite agents against the topic.

    Each elite receives the vibes, kill shot, AND swarm census.
    They must respond within their domain expertise.
    """
    # Auto-select relevant elites
    active_ids = await select_relevant_elites(topic)

    vibes_text = "\n".join([
        f"- {v.get('label', '?')} ({v.get('post_count', 0)} posts): {v.get('core_belief', 'N/A')}"
        for v in vibes[:5]
    ])

    kill_text = json.dumps(kill_shot, indent=2, default=str)[:500]

    swarm_text = json.dumps(swarm_summary, indent=2, default=str)[:500]

    context = f"""TOPIC: {topic}

SOCIAL PERSONAS (compressed from {swarm_summary.get('total_citizens', 0)} citizens):
{vibes_text}

SHADOW SWARM CENSUS:
- Bull: {swarm_summary.get('bull_pct', 0)}% | Bear: {swarm_summary.get('bear_pct', 0)}% | Neutral: {swarm_summary.get('neutral_pct', 0)}%
- Average Sentiment: {swarm_summary.get('avg_sentiment', 0)}
- Top Emotions: {swarm_summary.get('top_emotions', [])}

BLACKSWAN KILL SHOT (you must DEFEND or CONFIRM this threat):
{kill_text}

Analyze from YOUR domain expertise. If the Kill Shot is valid in your domain, confirm it. If not, explain why it fails."""

    results = {}
    for elite_id in active_ids:
        elite = ELITE_REGISTRY.get(elite_id)
        if not elite:
            continue

        try:
            response, model = await smart_chat(
                prompt=context,
                system=elite["system"],
                json_mode=True,
                force_model="nexus",  # mistral-small:24b — elite analysis
            )
            try:
                results[elite_id] = json.loads(response)
            except json.JSONDecodeError:
                results[elite_id] = {"raw": response[:500]}

            results[elite_id]["_agent_name"] = elite["name"]
            results[elite_id]["_model_used"] = model

        except Exception as e:
            results[elite_id] = {"error": str(e)[:200], "_agent_name": elite["name"]}

    return results
