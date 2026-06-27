"""Cognitive Dissonance Matrix — The Alpha Generator.

Most systems fail because they seek consensus. We seek the WIDEST GAP.

| Metric              | Calculation                         | Meaning                                          |
|---------------------|-------------------------------------|--------------------------------------------------|
| Delta 1 (The Trap)  | Swarm_Sentiment - Elite_Sentiment   | Crowd exuberant + experts scared = TOP IS IN     |
| Delta 2 (The Blindspot) | Consensus - BlackSwan_Feasibility | Everyone ignoring the Kill Shot = Black Swan risk |
| Delta 3 (The Chaos) | Variance(Elite_Opinions)            | Experts guessing = High Volatility                |

The Antifragile Output:
"The entire Bull Case rests on [Linchpin]. The Swarm is 90% Bullish, but the
Assassin found a 12% probability of [Kill Shot]. Action: [Antifragile Play]."
"""


def calculate_cognitive_dissonance(
    swarm_summary: dict,
    elite_results: dict,
    kill_shot: dict,
) -> dict:
    """Calculate the Cognitive Dissonance Matrix.

    This is the Alpha Generator. High dissonance = HIGH VOLATILITY = most valuable signal.
    """
    swarm_sentiment = swarm_summary.get("avg_sentiment", 0)
    swarm_bull_pct = swarm_summary.get("bull_pct", 50)
    swarm_bear_pct = swarm_summary.get("bear_pct", 20)
    kill_probability = kill_shot.get("probability", 0.1)
    kill_impact = kill_shot.get("impact_score", 0.5)
    kill_trigger = kill_shot.get("trigger", "Unknown")
    antifragile_play = kill_shot.get("antifragile_play", "No play identified")

    # Extract elite sentiments
    elite_sentiments = {}
    for elite_id, result in elite_results.items():
        if isinstance(result, dict):
            direction = _extract_direction(result)
            elite_sentiments[elite_id] = direction

    # Count bull vs bear among elites
    elite_bulls = sum(1 for v in elite_sentiments.values() if v > 0)
    elite_bears = sum(1 for v in elite_sentiments.values() if v < 0)
    elite_total = max(len(elite_sentiments), 1)
    elite_bull_pct = elite_bulls / elite_total * 100
    elite_bear_pct = elite_bears / elite_total * 100

    # ============================================================
    # DELTA 1: THE TRAP
    # Swarm_Sentiment - Elite_Sentiment
    # If high (+): crowd is exuberant, experts are scared. TOP IS IN.
    # If low (-): crowd is panicking, experts are calm. BOTTOM signal.
    # ============================================================
    the_trap = swarm_bull_pct - elite_bull_pct

    if the_trap > 30:
        trap_signal = "EXTREME DIVERGENCE — Crowd euphoria while experts retreat. Classic top signal."
    elif the_trap > 15:
        trap_signal = "HIGH — Crowd more bullish than experts. Distribution phase possible."
    elif the_trap < -30:
        trap_signal = "EXTREME REVERSAL — Crowd panicking while experts accumulate. Possible bottom."
    elif the_trap < -15:
        trap_signal = "REVERSAL HINT — Experts more bullish than crowd. Smart money loading."
    else:
        trap_signal = "ALIGNED — Crowd and experts in agreement. Trend continuation likely."

    # ============================================================
    # DELTA 2: THE BLINDSPOT
    # Consensus_Strength - BlackSwan_Feasibility
    # If high (+): everyone ignoring the Kill Shot. Black Swan risk is REAL.
    # ============================================================
    consensus_strength = max(swarm_bull_pct, swarm_bear_pct)  # How strong one-sided the crowd is
    kill_feasibility = kill_probability * kill_impact * 100
    the_blindspot = consensus_strength - (100 - kill_feasibility)

    if the_blindspot > 40:
        blindspot_signal = "CRITICAL — Strong consensus + viable Kill Shot = everyone is sleeping on the risk."
    elif the_blindspot > 20:
        blindspot_signal = "HIGH — Consensus is ignoring a non-trivial threat. Watch closely."
    elif the_blindspot > 0:
        blindspot_signal = "MODERATE — Some awareness of risk but crowd hasn't priced it in."
    else:
        blindspot_signal = "LOW — Kill Shot is either low-probability or crowd has already absorbed it."

    # ============================================================
    # DELTA 3: THE CHAOS
    # Variance(Elite_Opinions)
    # If high: even the experts are guessing. High Volatility regime.
    # ============================================================
    if elite_sentiments:
        the_chaos = _variance(list(elite_sentiments.values())) * 100
    else:
        the_chaos = 50  # No data = assume chaos

    if the_chaos > 60:
        chaos_signal = "MAXIMUM CHAOS — Experts fundamentally disagree. Volatility regime. Trade small or hedge."
    elif the_chaos > 40:
        chaos_signal = "HIGH CHAOS — Significant expert disagreement. Multiple scenarios equally likely."
    elif the_chaos > 20:
        chaos_signal = "MODERATE — Some expert disagreement but a weak consensus exists."
    else:
        chaos_signal = "LOW — Experts mostly aligned. Directional conviction is high."

    # ============================================================
    # COMPOSITE DISSONANCE SCORE
    # ============================================================
    score = (
        abs(the_trap) * 0.35 +
        abs(the_blindspot) * 0.35 +
        the_chaos * 0.30
    )
    score = min(100, max(0, score))

    # Determine volatility regime
    if score > 70:
        volatility = "EXTREME"
        action = f"Execute Antifragile Play: {antifragile_play}"
    elif score > 50:
        volatility = "HIGH"
        action = "Reduce position sizes. Hedge directional exposure. Watch for catalyst."
    elif score > 30:
        volatility = "ELEVATED"
        action = "Monitor. Set alerts on Kill Shot trigger conditions."
    else:
        volatility = "LOW"
        action = "Trend continuation likely. Standard risk management."

    # Build the Antifragile Output
    linchpin = kill_shot.get("trigger", "Unknown")
    antifragile_output = (
        f"The entire {'Bull' if swarm_bull_pct > 60 else 'Bear'} Case rests on: {linchpin}. "
        f"The Swarm is {swarm_bull_pct:.0f}% Bullish, but the Assassin found a "
        f"{kill_probability*100:.0f}% probability of {kill_trigger[:80]}. "
        f"Action: {action}"
    )

    return {
        "score": round(score, 1),
        "volatility_regime": volatility,
        "antifragile_output": antifragile_output,
        "action": action,
        "matrix": {
            "delta_1_the_trap": {
                "value": round(the_trap, 1),
                "signal": trap_signal,
                "swarm_bull": round(swarm_bull_pct, 1),
                "elite_bull": round(elite_bull_pct, 1),
            },
            "delta_2_the_blindspot": {
                "value": round(the_blindspot, 1),
                "signal": blindspot_signal,
                "consensus_strength": round(consensus_strength, 1),
                "kill_feasibility": round(kill_feasibility, 1),
            },
            "delta_3_the_chaos": {
                "value": round(the_chaos, 1),
                "signal": chaos_signal,
                "elite_breakdown": elite_sentiments,
            },
        },
        "kill_shot_summary": {
            "trigger": kill_trigger,
            "probability": kill_probability,
            "impact": kill_impact,
            "antifragile_play": antifragile_play,
        },
        "linchpin": linchpin,
    }


def _extract_direction(result: dict) -> float:
    """Extract a bull/bear direction from an elite agent's output."""
    for key in ["market_impact", "direction", "crypto_impact", "macro_assessment",
                 "startup_impact", "geopolitical_impact", "cultural_impact",
                 "trade_setup", "regulatory_risk", "tech_assessment"]:
        val = result.get(key, "")
        if isinstance(val, str):
            val_lower = val.lower()
            if any(w in val_lower for w in ["bullish", "positive", "up", "growth", "opportunity",
                                             "stabilizing", "long", "expanding", "hot"]):
                return 1.0
            if any(w in val_lower for w in ["bearish", "negative", "down", "threat", "destabilizing",
                                             "collapse", "short", "contracting", "frozen", "high"]):
                return -1.0
    return 0.0


def _variance(values: list) -> float:
    if not values:
        return 0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)
