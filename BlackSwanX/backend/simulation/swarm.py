"""Shadow Swarm — Wave-based citizen simulation.

Loads 20 citizens at a time to manage M2 Pro RAM.
Each citizen gets a unique persona and reacts to the topic with BIAS.
The BlackSwan's Kill Shot is presented to see if citizens can "feel" the risk.
"""
import json
import random
from backend.llm.router import smart_chat
from backend.llm.prompts import CITIZEN_SYSTEM

# Diverse persona templates for 200+ citizens
PERSONA_TEMPLATES = [
    # Age / background variations
    "a 22-year-old crypto-native college dropout who made $50K on meme coins",
    "a 45-year-old middle manager at a Fortune 500 who lost money in 2008",
    "a 67-year-old retired teacher who watches CNBC every morning",
    "a 30-year-old startup founder burning through Series A cash",
    "a 55-year-old union factory worker worried about automation",
    "a 19-year-old TikTok trader who learned investing from YouTube",
    "a 38-year-old single mom working two jobs, no savings",
    "a 42-year-old hedge fund analyst who thinks retail is dumb money",
    "a 28-year-old data scientist at a FAANG company",
    "a 60-year-old small business owner with 3 employees",
    # Political / worldview variations
    "a libertarian software engineer who distrusts all regulation",
    "a progressive activist who sees corporate greed everywhere",
    "a centrist policy wonk who reads The Economist religiously",
    "a MAGA supporter who thinks the media lies about everything",
    "a European social democrat who wants Nordic-model everything",
    # Personality variations
    "a perpetual optimist who has never sold a stock at a loss",
    "a doom-and-gloom prepper who thinks collapse is always near",
    "a cynical Reddit mod who has seen every hype cycle crash",
    "a hyped VC intern who thinks every startup is 'disrupting'",
    "a cautious retail dev who only buys index funds",
    "a FOMO-driven day trader who chases every pump",
    "a contrarian who automatically takes the opposite position",
    "a conspiracy theorist who connects everything to 'them'",
    "a pragmatic CFO who only cares about cash flow and margins",
    "a Gen Z influencer who measures everything in engagement",
    # Regional / cultural variations
    "a Wall Street veteran who dismisses Silicon Valley hype",
    "a Shenzhen hardware founder who thinks Western tech is slow",
    "an Indian SaaS founder bootstrapping with $2K MRR",
    "a Lagos fintech user who relies on mobile money",
    "a Berlin climate activist who opposes all fossil fuel investment",
    "a Tokyo salaryman who invests 10% in safe bonds",
    "a Dubai crypto whale who moves markets with single trades",
    "a rural American farmer worried about trade wars",
    "a London banker who thinks fintech is overhyped",
    "a Sao Paulo Uber driver who day-trades on Robinhood",
    # Expertise variations
    "a PhD economist who writes papers nobody reads",
    "a patent lawyer who sees IP risk in everything",
    "a cybersecurity researcher who finds vulnerabilities in everything",
    "a marketing VP who thinks brand perception is all that matters",
    "a supply chain manager who knows where the bottlenecks are",
]


def _generate_persona(wave_number: int, index: int) -> str:
    """Generate a unique persona for a citizen agent."""
    base = PERSONA_TEMPLATES[(wave_number * 20 + index) % len(PERSONA_TEMPLATES)]
    # Add random modifiers for uniqueness
    modifiers = [
        f"Currently feeling {'bullish' if random.random() > 0.5 else 'bearish'}.",
        f"Last big decision was {'right' if random.random() > 0.4 else 'wrong'}.",
        f"Trusts {'social media' if random.random() > 0.5 else 'mainstream media'} more.",
        f"Risk tolerance: {'high' if random.random() > 0.6 else 'low'}.",
    ]
    return f"{base}. {random.choice(modifiers)}"


async def run_swarm_wave(
    topic: str,
    vibes: list,
    kill_shot: dict,
    wave_size: int = 20,
    wave_number: int = 0,
) -> dict:
    """Run a single wave of citizen agents.

    Each citizen reads the vibes + kill shot context and reacts from their persona.
    Uses the CLUSTER model (cheap/fast) to keep RAM low.
    """
    vibes_text = "\n".join([
        f"- {v.get('label', '?')}: {v.get('core_belief', 'N/A')}"
        for v in vibes[:5]
    ])

    kill_text = kill_shot.get("trigger", "Unknown threat")

    context = f"""TOPIC: {topic}

CURRENT PUBLIC VIBES:
{vibes_text}

HIDDEN RISK (BlackSwan identified): {kill_text}

React to this situation based on your persona. What's your gut feeling?"""

    citizens = []
    for i in range(wave_size):
        persona = _generate_persona(wave_number, i)
        system = CITIZEN_SYSTEM.format(profile=persona)

        try:
            response, _ = await smart_chat(
                prompt=context,
                system=system,
                json_mode=True,
                force_model="swarm",  # llama3.2:3b — fast citizen simulation
                temperature=0.9,  # High temp for diversity
                max_tokens=256,  # Short responses to save RAM
            )
            try:
                citizen_data = json.loads(response)
            except json.JSONDecodeError:
                citizen_data = {
                    "gut_feeling": response[:200],
                    "sentiment": 0,
                    "emotion": "confused",
                    "confidence": 50,
                }

            citizen_data["persona"] = persona
            citizen_data["wave"] = wave_number
            citizen_data["index"] = i
            citizens.append(citizen_data)

        except Exception as e:
            citizens.append({
                "persona": persona,
                "gut_feeling": f"[Error: {str(e)[:100]}]",
                "sentiment": 0,
                "emotion": "error",
                "confidence": 0,
                "wave": wave_number,
                "index": i,
            })

    # Wave-level aggregation
    sentiments = [c.get("sentiment", 0) for c in citizens if isinstance(c.get("sentiment"), (int, float))]
    avg_sentiment = sum(sentiments) / max(len(sentiments), 1)

    return {
        "wave_number": wave_number,
        "citizen_count": len(citizens),
        "citizens": citizens,
        "avg_sentiment": round(avg_sentiment, 3),
        "bull_count": sum(1 for s in sentiments if s > 0.2),
        "bear_count": sum(1 for s in sentiments if s < -0.2),
    }
