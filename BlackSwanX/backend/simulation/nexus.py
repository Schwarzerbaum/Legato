"""NEXUS Orchestrator — The DAG Brain that manages STATE, not scripts.

Pipeline:
1. ANALYZE NOISE — crawl, detect if data is signal or noise, re-crawl if needed
2. VIBE COMPRESSION — 10K posts -> 5 Social Personas
3. THE ASSASSIN'S MARK — BlackSwan sets the Kill Goal EARLY (before swarm)
4. SWARM DEPLOYMENT — Wave-based (20 citizens at a time for RAM management)
5. ELITE PANEL — Domain experts analyze swarm + defend against kill shot
6. COGNITIVE DISSONANCE — Calculate Delta between bulls and assassins
7. SYNTHESIS — NEXUS builds the DAG and Decision-Ready Map

Key insight from Gemini: The BlackSwan doesn't wait for the end.
It sets the "Kill Goal" early, and the Elites must DEFEND against it.
"""
import json
import time
from dataclasses import dataclass, field
from enum import Enum


class PipelineState(Enum):
    IDLE = "idle"
    CRAWLING = "crawling"
    NOISE_CHECK = "noise_check"
    RE_CRAWLING = "re_crawling"
    COMPRESSING = "compressing"
    ASSASSIN_MARK = "assassin_mark"
    SWARM_RUNNING = "swarm_running"
    ELITE_PANEL = "elite_panel"
    DELTA_CALC = "delta_calc"
    SYNTHESIS = "synthesis"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class NexusState:
    """Full state of a NEXUS pipeline run. This is the brain."""
    topic: str
    state: PipelineState = PipelineState.IDLE
    crawl_attempts: int = 0
    max_crawl_attempts: int = 3

    # Stage outputs
    raw_posts: list = field(default_factory=list)
    platform_stats: dict = field(default_factory=dict)
    is_noise: bool = False
    vibes: list = field(default_factory=list)  # Social Personas
    kill_shot: dict = field(default_factory=dict)  # BlackSwan's early mark
    swarm_waves: list = field(default_factory=list)  # List of wave results
    elite_results: dict = field(default_factory=dict)  # Per-elite outputs
    cognitive_dissonance: dict = field(default_factory=dict)
    dag: list = field(default_factory=list)
    final_synthesis: dict = field(default_factory=dict)

    # Neural organism state
    neural_state: dict = field(default_factory=dict)  # Pheromone/signal activity

    # Metrics
    total_tokens: int = 0
    start_time: float = 0
    elapsed_seconds: float = 0
    events: list = field(default_factory=list)  # Log of state transitions

    def log(self, msg: str):
        self.events.append({"time": time.time() - self.start_time, "state": self.state.value, "msg": msg})

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "state": self.state.value,
            "crawl_attempts": self.crawl_attempts,
            "post_count": len(self.raw_posts),
            "platform_stats": self.platform_stats,
            "is_noise": self.is_noise,
            "vibe_count": len(self.vibes),
            "kill_shot": self.kill_shot,
            "swarm_waves_completed": len(self.swarm_waves),
            "elite_results_count": len(self.elite_results),
            "cognitive_dissonance": self.cognitive_dissonance,
            "dag": self.dag,
            "total_tokens": self.total_tokens,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "events": self.events[-20:],  # Last 20 events
        }


async def run_nexus_pipeline(
    topic: str,
    db=None,
    on_state_change=None,
) -> NexusState:
    """Run the full NEXUS pipeline with state management.

    on_state_change: callback(state: NexusState) for real-time UI updates.
    """
    from backend.crawler.unified import crawl_all_platforms, platform_stats
    from backend.compression.embedder import embed_posts
    from backend.compression.clusterer import cluster_posts, get_cluster_representatives
    from backend.compression.summarizer import compress_all_clusters
    from backend.simulation.swarm import run_swarm_wave
    from backend.simulation.elite_panel import run_elite_panel
    from backend.simulation.delta import calculate_cognitive_dissonance
    from backend.llm.router import smart_chat
    from backend.llm.prompts import NEXUS_ORCHESTRATOR_SYSTEM, BLACKSWAN_ASSASSIN_SYSTEM

    ns = NexusState(topic=topic, start_time=time.time())

    def update(new_state: PipelineState, msg: str = ""):
        ns.state = new_state
        ns.elapsed_seconds = time.time() - ns.start_time
        ns.log(msg or new_state.value)
        if on_state_change:
            on_state_change(ns)

    # ============================================================
    # STAGE 1: CRAWL + NOISE CHECK
    # ============================================================
    while ns.crawl_attempts < ns.max_crawl_attempts:
        ns.crawl_attempts += 1
        update(PipelineState.CRAWLING, f"Crawl attempt {ns.crawl_attempts}")

        posts = await crawl_all_platforms(topic, max_per_platform=100)
        ns.raw_posts = posts
        ns.platform_stats = platform_stats(posts)

        if len(posts) < 10:
            update(PipelineState.NOISE_CHECK, f"Only {len(posts)} posts — noise detected")
            ns.is_noise = True
            # Ask NEXUS if we should re-crawl with different terms
            noise_check, _ = await smart_chat(
                prompt=f"Topic: '{topic}' returned only {len(posts)} results from {ns.platform_stats}. Is this noise? If yes, suggest 3 better search terms.",
                system="You are a search quality analyst. Output JSON: {\"is_noise\": true/false, \"better_terms\": [\"term1\", \"term2\", \"term3\"]}",
                json_mode=True,
                force_model="swarm",
            )
            try:
                noise_data = json.loads(noise_check)
                if noise_data.get("is_noise") and noise_data.get("better_terms"):
                    topic = noise_data["better_terms"][0]  # Re-crawl with better term
                    update(PipelineState.RE_CRAWLING, f"Re-crawling with: {topic}")
                    continue
            except json.JSONDecodeError:
                pass

        ns.is_noise = False
        update(PipelineState.NOISE_CHECK, f"Signal detected: {len(posts)} posts from {ns.platform_stats}")
        break

    if ns.is_noise:
        update(PipelineState.FAILED, "Could not find signal after max crawl attempts")
        return ns

    # ============================================================
    # STAGE 2: VIBE COMPRESSION
    # ============================================================
    update(PipelineState.COMPRESSING, "Embedding and clustering posts...")

    embeddings = await embed_posts(ns.raw_posts)
    labels = cluster_posts(embeddings, n_clusters=5)

    for i, p in enumerate(ns.raw_posts):
        p["cluster"] = int(labels[i])

    clusters = get_cluster_representatives(ns.raw_posts, embeddings, labels)
    ns.vibes = await compress_all_clusters(clusters, topic)

    update(PipelineState.COMPRESSING, f"Compressed into {len(ns.vibes)} Social Personas")

    # ============================================================
    # STAGE 3: THE ASSASSIN'S MARK (BlackSwan sets Kill Goal EARLY)
    # ============================================================
    update(PipelineState.ASSASSIN_MARK, "BlackSwan Assassin identifying the Kill Shot...")

    vibes_context = "\n".join([
        f"Persona: {v.get('label')} ({v.get('post_count')} posts) - {v.get('core_belief', 'N/A')}"
        for v in ns.vibes
    ])

    kill_response, _ = await smart_chat(
        prompt=f"Topic: {topic}\n\nSocial Personas from {len(ns.raw_posts)} posts:\n{vibes_context}\n\nFind the Kill Shot. What LPHI event would collapse the current narrative?",
        system=BLACKSWAN_ASSASSIN_SYSTEM,
        json_mode=True,
        force_model="assassin",  # phi4:14b — deep reasoning for kill shots
    )

    try:
        ns.kill_shot = json.loads(kill_response)
    except json.JSONDecodeError:
        ns.kill_shot = {"trigger": kill_response[:500], "cascade": [], "probability": 0.1}

    update(PipelineState.ASSASSIN_MARK, f"Kill Shot: {ns.kill_shot.get('trigger', 'identified')[:100]}")

    # ============================================================
    # STAGE 4: SWARM DEPLOYMENT (Wave-based, 20 at a time)
    # ============================================================
    update(PipelineState.SWARM_RUNNING, "Deploying Shadow Swarm in waves...")

    total_citizens = 200
    wave_size = 20
    wave_count = total_citizens // wave_size

    for wave_num in range(wave_count):
        update(PipelineState.SWARM_RUNNING, f"Wave {wave_num + 1}/{wave_count} ({wave_size} citizens)")

        wave_result = await run_swarm_wave(
            topic=topic,
            vibes=ns.vibes,
            kill_shot=ns.kill_shot,
            wave_size=wave_size,
            wave_number=wave_num,
        )
        ns.swarm_waves.append(wave_result)

        # CRITICAL: Flush GPU cache between waves for M2 Pro stability
        from backend.llm.client import flush_gpu_cache
        await flush_gpu_cache("cluster")

    update(PipelineState.SWARM_RUNNING, f"Swarm complete: {len(ns.swarm_waves)} waves, {total_citizens} citizens")

    # ============================================================
    # STAGE 5: ELITE PANEL
    # ============================================================
    update(PipelineState.ELITE_PANEL, "Running Elite Panel analysis...")

    # Aggregate swarm results for elites
    swarm_summary = _aggregate_swarm(ns.swarm_waves)

    ns.elite_results = await run_elite_panel(
        topic=topic,
        vibes=ns.vibes,
        kill_shot=ns.kill_shot,
        swarm_summary=swarm_summary,
    )

    update(PipelineState.ELITE_PANEL, f"Elite Panel complete: {len(ns.elite_results)} experts responded")

    # ============================================================
    # STAGE 6: COGNITIVE DISSONANCE SCORE
    # ============================================================
    update(PipelineState.DELTA_CALC, "Calculating Cognitive Dissonance...")

    ns.cognitive_dissonance = calculate_cognitive_dissonance(
        swarm_summary=swarm_summary,
        elite_results=ns.elite_results,
        kill_shot=ns.kill_shot,
    )

    update(PipelineState.DELTA_CALC, f"Dissonance Score: {ns.cognitive_dissonance.get('score', 'N/A')}")

    # ============================================================
    # STAGE 7: NEXUS SYNTHESIS
    # ============================================================
    update(PipelineState.SYNTHESIS, "NEXUS synthesizing final DAG...")

    synthesis_prompt = f"""TOPIC: {topic}

SOCIAL PERSONAS: {json.dumps([{{'label': v.get('label'), 'belief': v.get('core_belief'), 'count': v.get('post_count')}} for v in ns.vibes])}

KILL SHOT: {json.dumps(ns.kill_shot)}

SWARM CENSUS: {json.dumps(swarm_summary)}

ELITE PANEL RESULTS: {json.dumps(ns.elite_results, default=str)[:3000]}

COGNITIVE DISSONANCE: {json.dumps(ns.cognitive_dissonance)}

Build the final DAG. Identify the Linchpin. Map the critical path. Output actionable intelligence."""

    synthesis_response, _ = await smart_chat(
        prompt=synthesis_prompt,
        system=NEXUS_ORCHESTRATOR_SYSTEM,
        json_mode=True,
        force_model="nexus",  # mistral-small:24b — the synthesis brain
    )

    try:
        ns.final_synthesis = json.loads(synthesis_response)
    except json.JSONDecodeError:
        ns.final_synthesis = {"raw": synthesis_response[:2000]}

    ns.dag = ns.final_synthesis.get("dag", [])

    # ============================================================
    # STAGE 8: SONA AUDIT (System Auditor)
    # ============================================================
    update(PipelineState.SYNTHESIS, "SONA auditing all agents...")

    from backend.simulation.sona import audit_pipeline
    await audit_pipeline(
        pipeline_id=f"nexus_{int(time.time())}",
        topic=topic,
        topic_domain=_detect_domain(topic),
        swarm_waves=ns.swarm_waves,
        elite_results=ns.elite_results,
        kill_shot=ns.kill_shot,
        cognitive_dissonance=ns.cognitive_dissonance,
    )

    # ============================================================
    # STAGE 9: NEURAL ORGANISM TICK
    # ============================================================
    update(PipelineState.SYNTHESIS, "Neural organism processing signals...")

    try:
        from backend.neural.integration import get_event_bus, run_neural_tick

        bus = get_event_bus()

        # Deposit pheromones from pipeline results
        await bus.emit("pipeline_stage", {"stage": "crawl", "posts": len(ns.raw_posts)}, "LOW", "nexus_orchestrator")
        await bus.emit("pipeline_stage", {"stage": "kill_shot", "trigger": ns.kill_shot.get("trigger", "")}, "CRITICAL", "nexus_orchestrator")

        dissonance_score = ns.cognitive_dissonance.get("score", 0)
        if dissonance_score > 60:
            await bus.emit("anomaly_detected", {"dissonance_score": dissonance_score, "score": dissonance_score / 100}, "HIGH", "nexus_orchestrator")

        # Run neural tick — evaporate, transmit, myelinate
        tick_result = await run_neural_tick(db)
        ns.neural_state = tick_result
        ns.log(f"Neural tick: {tick_result.get('signals_propagated', 0)} signals, {tick_result.get('pathways_myelinated', 0)} myelinated")
    except Exception as e:
        ns.log(f"Neural tick skipped: {e}")
        ns.neural_state = {"error": str(e)}

    update(PipelineState.COMPLETE, "NEXUS pipeline complete (SONA audit saved, neural tick processed)")
    ns.elapsed_seconds = time.time() - ns.start_time
    return ns


def _detect_domain(topic: str) -> str:
    """Simple domain detection from topic keywords."""
    topic_lower = topic.lower()
    domains = {
        "finance": ["stock", "market", "trading", "bitcoin", "crypto", "price", "invest", "fund", "ipo", "earnings"],
        "tech": ["ai", "software", "startup", "app", "platform", "developer", "code", "saas", "cloud"],
        "politics": ["election", "policy", "government", "regulation", "law", "vote", "democrat", "republican"],
        "social": ["culture", "trend", "viral", "social media", "influencer", "brand", "reputation"],
        "geopolitics": ["war", "sanctions", "china", "russia", "trade war", "nato", "military"],
        "health": ["vaccine", "pandemic", "health", "fda", "drug", "pharma", "medical"],
    }
    for domain, keywords in domains.items():
        if any(k in topic_lower for k in keywords):
            return domain
    return "general"


def _aggregate_swarm(waves: list) -> dict:
    """Aggregate all swarm wave results into a census."""
    all_opinions = []
    sentiment_sum = 0
    emotion_counts = {}
    bull_count = 0
    bear_count = 0

    for wave in waves:
        for citizen in wave.get("citizens", []):
            all_opinions.append(citizen.get("gut_feeling", ""))
            sent = citizen.get("sentiment", 0)
            sentiment_sum += sent
            if sent > 0.2:
                bull_count += 1
            elif sent < -0.2:
                bear_count += 1

            emotion = citizen.get("emotion", "neutral")
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

    total = max(len(all_opinions), 1)
    return {
        "total_citizens": total,
        "avg_sentiment": round(sentiment_sum / total, 3),
        "bull_pct": round(bull_count / total * 100, 1),
        "bear_pct": round(bear_count / total * 100, 1),
        "neutral_pct": round((total - bull_count - bear_count) / total * 100, 1),
        "top_emotions": sorted(emotion_counts.items(), key=lambda x: -x[1])[:5],
        "sample_opinions": all_opinions[:10],
    }
