"""Decision-Ready Map Generator.

NOT a summary of what happened — a map of WHERE THE FUTURE COULD CHANGE.

Structure:
1. Executive Summary (3 sentences)
2. Social Personas (the 5 Vibes)
3. BlackSwanX Flow (cross-platform idea movement)
4. Pressure Points (where outcomes diverge)
5. Kill-Switch Result (Volatility Score)
6. Prediction Scenarios (most likely, best, worst)
7. Black Swans (stress-test results)
8. Action Items (what to watch)
"""
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database.models import (
    Topic, SocialPersona, Simulation, SimulationRound, Report
)
from backend.llm.router import smart_chat
from backend.llm.prompts import REPORT_SYSTEM


async def generate_report(
    topic_id: int,
    simulation_id: int,
    db: AsyncSession,
    kill_switch_result: dict = None,
    blackswan_result: dict = None,
) -> dict:
    """Generate a Decision-Ready Map from simulation results."""

    topic = await db.get(Topic, topic_id)
    if not topic:
        return {"error": "Topic not found"}

    # Gather personas
    result = await db.execute(
        select(SocialPersona).where(SocialPersona.topic_id == topic_id)
    )
    personas = result.scalars().all()

    # Gather simulation rounds
    result = await db.execute(
        select(SimulationRound)
        .where(SimulationRound.simulation_id == simulation_id)
        .order_by(SimulationRound.round_number)
    )
    rounds = result.scalars().all()

    # Build context for report generation
    personas_text = "\n".join([
        f"**{p.label}** ({p.post_count} posts, sentiment: {p.avg_sentiment:.1f}): "
        f"{json.loads(p.vibe_summary).get('core_belief', 'N/A') if p.vibe_summary else 'N/A'}"
        for p in personas
    ])

    rounds_text = ""
    last_synthesis = ""
    last_challenge = ""
    for r in rounds:
        rounds_text += f"\n### Round {r.round_number}\n"
        rounds_text += f"**Moderator Synthesis:** {(r.moderator_synthesis or '')[:500]}\n"
        rounds_text += f"**Self-Critique:** {(r.recursive_challenge or '')[:300]}\n"
        last_synthesis = r.moderator_synthesis or ""
        last_challenge = r.recursive_challenge or ""

    kill_text = ""
    if kill_switch_result:
        ks = kill_switch_result
        vol = ks.get("volatility_score", "N/A")
        verdict = ks.get("verdict", {})
        kill_text = f"""
**Volatility Score: {vol}**
Verdict: {verdict.get('verdict', 'N/A')}
Critical Variable: {verdict.get('critical_variable', 'N/A')}
Fans Hype Score: {ks.get('fans', {}).get('hype_score', 'N/A')}
Assassins Kill Shot: {ks.get('assassins', {}).get('kill_shot', 'N/A')}
"""

    blackswan_text = ""
    if blackswan_result:
        bs = blackswan_result
        blackswan_text = f"""
**Robustness Score: {bs.get('robustness_score', 'N/A')}**
Most Dangerous Swan: {bs.get('most_dangerous_swan', 'N/A')}
"""
        for swan in bs.get("black_swans", [])[:3]:
            blackswan_text += f"- {swan.get('event', 'N/A')} (P={swan.get('probability', '?')}, Impact={swan.get('impact_score', '?')})\n"

    # Generate the report via LLM
    prompt = f"""Generate a Decision-Ready Map for:

TOPIC: {topic.query}

SOCIAL PERSONAS:
{personas_text}

SIMULATION RESULTS:
{rounds_text}

KILL-SWITCH ANALYSIS:
{kill_text}

BLACK SWAN STRESS TEST:
{blackswan_text}

Generate the full report in Markdown. Focus on ACTIONABLE pressure points, not summaries."""

    report_md, model = await smart_chat(
        prompt=prompt,
        system=REPORT_SYSTEM,
        force_model="reasoning",
        max_tokens=4096,
    )

    # Extract pressure points from the last synthesis
    pressure_points = []
    try:
        synthesis = json.loads(last_synthesis)
        pressure_points = synthesis.get("pressure_points", [])
    except (json.JSONDecodeError, TypeError):
        pass

    # Save report
    report = Report(
        topic_id=topic_id,
        simulation_id=simulation_id,
        title=f"Decision-Ready Map: {topic.query}",
        content_md=report_md,
        content_html=_md_to_basic_html(report_md),
        pressure_points={"points": pressure_points},
        token_usage={"model": model, "generated_at": datetime.utcnow().isoformat()},
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return {
        "report_id": report.id,
        "title": report.title,
        "content_md": report_md,
        "pressure_points": pressure_points,
    }


def _md_to_basic_html(md: str) -> str:
    """Very basic Markdown to HTML. For proper rendering, use frontend."""
    html = md
    # Headers
    for i in range(6, 0, -1):
        prefix = "#" * i
        html = html.replace(f"\n{prefix} ", f"\n<h{i}>")
        # Close tags roughly (the frontend will do proper rendering)
    # Bold
    import re
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    # Line breaks
    html = html.replace("\n", "<br>\n")
    return f"<div class='report'>{html}</div>"
