"""Simulation Engine — orchestrates the full analysis + prediction pipeline.

Pipeline:
1. Crawl data from all platforms
2. Embed + Cluster → Social Personas (Semantic Compression)
3. Run Mirror Simulation (3 adversarial agents + moderator)
4. Temporal Recursive Loop (self-critique)
5. Narrative Kill-Switch (Fans vs Assassins)
6. BlackSwan stress test
7. Generate Decision-Ready Map
"""
import json
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Topic, RawPost, SocialPersona, Simulation, SimulationRound
from backend.crawler.unified import crawl_all_platforms, platform_stats
from backend.compression.embedder import embed_posts
from backend.compression.clusterer import cluster_posts, get_cluster_representatives
from backend.compression.summarizer import compress_all_clusters
from backend.simulation.kill_switch import run_kill_switch
from backend.simulation.blackswan import inject_black_swans
from backend.simulation.sona import self_optimize_prompt
from backend.llm.router import smart_chat
from backend.llm.prompts import (
    PROVOCATEUR_SYSTEM, WHALE_SYSTEM, CATALYST_SYSTEM,
    MODERATOR_SYSTEM, RECURSIVE_CHALLENGE_SYSTEM,
)


async def run_full_pipeline(
    topic_id: int,
    db: AsyncSession,
    on_status=None,
) -> dict:
    """Run the complete BlackSwanX pipeline for a topic.

    on_status: optional callback(stage: str, detail: str) for progress updates.
    """
    topic = await db.get(Topic, topic_id)
    if not topic:
        return {"error": "Topic not found"}

    def status(stage, detail=""):
        if on_status:
            on_status(stage, detail)

    # === STAGE 1: Crawl ===
    status("crawling", "Searching web, Reddit, news...")
    topic.status = "crawling"
    await db.commit()

    posts = await crawl_all_platforms(topic.query, max_per_platform=100)
    stats = platform_stats(posts)
    status("crawling", f"Found {len(posts)} posts: {stats}")

    # Save posts to DB
    for p in posts:
        raw = RawPost(
            topic_id=topic_id,
            platform=p["platform"],
            author=p.get("author", ""),
            content=p["content"],
            url=p.get("url", ""),
            engagement=p.get("engagement", 0),
        )
        db.add(raw)
    await db.commit()

    # === STAGE 2: Semantic Compression ===
    status("compressing", "Embedding posts...")
    topic.status = "analyzing"
    await db.commit()

    embeddings = await embed_posts(posts)
    labels = cluster_posts(embeddings, n_clusters=5)

    # Assign cluster labels back to posts
    for i, p in enumerate(posts):
        p["cluster"] = int(labels[i])

    clusters = get_cluster_representatives(posts, embeddings, labels)
    status("compressing", f"Created {len(clusters)} Social Personas")

    personas = await compress_all_clusters(clusters, topic.query)

    # Save personas to DB
    for persona in personas:
        sp = SocialPersona(
            topic_id=topic_id,
            label=persona.get("label", "Unknown"),
            vibe_summary=json.dumps(persona, ensure_ascii=False),
            post_count=persona.get("post_count", 0),
            avg_sentiment=persona.get("avg_sentiment", 0.0),
            platforms=persona.get("platforms"),
            representative_quotes=persona.get("representative_quotes"),
        )
        db.add(sp)
    await db.commit()

    # === STAGE 3: Mirror Simulation ===
    status("simulating", "Running adversarial agent debate...")
    topic.status = "simulating"
    await db.commit()

    # Create simulation record
    sim = Simulation(topic_id=topic_id, total_rounds=3)
    db.add(sim)
    await db.commit()
    await db.refresh(sim)

    # Build compressed context from personas
    personas_context = "\n".join([
        f"Persona: {p.get('label')} ({p.get('post_count')} posts) - {p.get('core_belief', 'N/A')}"
        for p in personas
    ])

    context = f"Topic: {topic.query}\n\nSocial Personas:\n{personas_context}"

    # Get SONA-enhanced prompts
    prov_system = await self_optimize_prompt(PROVOCATEUR_SYSTEM, db)
    whale_system = await self_optimize_prompt(WHALE_SYSTEM, db)
    cat_system = await self_optimize_prompt(CATALYST_SYSTEM, db)

    for round_num in range(1, 4):
        status("simulating", f"Round {round_num}/3")

        # Run all three agents
        prov_resp, _ = await smart_chat(context, system=prov_system, json_mode=True, force_model="reasoning")
        whale_resp, _ = await smart_chat(context, system=whale_system, json_mode=True, force_model="reasoning")
        cat_resp, _ = await smart_chat(context, system=cat_system, json_mode=True, force_model="reasoning")

        # Moderator synthesis
        mod_prompt = f"""Agent Provocateur says:\n{prov_resp}\n\nSentiment Whale says:\n{whale_resp}\n\nCatalyst says:\n{cat_resp}"""
        mod_resp, _ = await smart_chat(mod_prompt, system=MODERATOR_SYSTEM, json_mode=True, force_model="reasoning")

        # Temporal Recursive Loop — argue against the synthesis
        recursive_resp, _ = await smart_chat(
            f"PREDICTION TO CHALLENGE:\n{mod_resp}",
            system=RECURSIVE_CHALLENGE_SYSTEM,
            json_mode=True,
            force_model="reasoning",
        )

        # Save round
        sim_round = SimulationRound(
            simulation_id=sim.id,
            round_number=round_num,
            provocateur_output=prov_resp,
            whale_output=whale_resp,
            catalyst_output=cat_resp,
            moderator_synthesis=mod_resp,
            recursive_challenge=recursive_resp,
        )
        db.add(sim_round)

        sim.current_round = round_num
        await db.commit()

        # Update context with moderator synthesis for next round
        context += f"\n\nRound {round_num} Synthesis: {mod_resp[:500]}"

    # === STAGE 4: Kill-Switch ===
    status("kill-switch", "Running Narrative Kill-Switch...")
    kill_result = await run_kill_switch(topic.query, personas_context)

    # === STAGE 5: BlackSwan ===
    status("blackswan", "Stress-testing with Black Swans...")
    blackswan_result = await inject_black_swans(
        f"Topic: {topic.query}\nPrediction: {mod_resp[:500]}"
    )

    sim.status = "complete"
    topic.status = "complete"
    await db.commit()

    status("complete", "Pipeline finished!")

    return {
        "topic_id": topic_id,
        "simulation_id": sim.id,
        "posts_crawled": len(posts),
        "personas": personas,
        "kill_switch": kill_result,
        "black_swans": blackswan_result,
        "platform_stats": stats,
    }
