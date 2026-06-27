"""Persona Summarizer — compress each cluster into a "Vibe" description.

This is where Semantic Compression meets LLM:
- Cluster of 2000 posts → 3 representative quotes → LLM → 1 "Vibe" (100 words)
- Only the Vibe gets sent to the reasoning model, not all 2000 posts.
"""
import json
from backend.llm.router import smart_chat
from backend.llm.prompts import PERSONA_COMPRESS_SYSTEM


async def summarize_persona(
    cluster_posts: list[dict],
    cluster_count: int,
    topic: str,
) -> dict:
    """Compress a cluster of posts into a single Social Persona / Vibe.

    Uses the CLUSTER model (cheap) for this task.
    """
    # Build context from representative posts
    quotes = []
    for p in cluster_posts[:5]:  # Max 5 representative posts
        content = p.get("content", "")[:300]
        platform = p.get("platform", "unknown")
        engagement = p.get("engagement", 0)
        quotes.append(f"[{platform}] (engagement: {engagement}) {content}")

    prompt = f"""Topic: {topic}
Cluster size: {cluster_count} posts

Representative quotes from this group:
{chr(10).join(quotes)}

Compress this group into a single Social Persona / "Vibe"."""

    response, model = await smart_chat(
        prompt=prompt,
        system=PERSONA_COMPRESS_SYSTEM,
        json_mode=True,
        force_model="cluster",  # Use cheap model
    )

    try:
        persona = json.loads(response)
    except json.JSONDecodeError:
        persona = {
            "label": f"Group {cluster_count}",
            "core_belief": response[:200],
            "emotional_tone": "mixed",
            "fears": [],
            "hopes": [],
            "avg_sentiment": 0.0,
        }

    persona["post_count"] = cluster_count
    persona["representative_quotes"] = [p.get("content", "")[:200] for p in cluster_posts[:3]]
    persona["platforms"] = _count_platforms(cluster_posts)
    return persona


async def compress_all_clusters(
    clusters: dict,
    topic: str,
) -> list[dict]:
    """Compress all clusters into Social Personas."""
    personas = []
    for cluster_id, cluster_data in clusters.items():
        persona = await summarize_persona(
            cluster_posts=cluster_data["posts"],
            cluster_count=cluster_data["count"],
            topic=topic,
        )
        persona["cluster_id"] = cluster_id
        personas.append(persona)

    # Sort by post count (largest group first)
    personas.sort(key=lambda p: p.get("post_count", 0), reverse=True)
    return personas


def _count_platforms(posts: list[dict]) -> dict:
    counts = {}
    for p in posts:
        platform = p.get("platform", "unknown")
        counts[platform] = counts.get(platform, 0) + 1
    return counts
