"""Semantic Router — route tasks to the cheapest sufficient model.

Simple summaries → tiny model (0.1% token load)
Complex reasoning → big model (DeepSeek-R1)

This is the key to running a 10-agent swarm on a laptop without lag.
"""
import re
from backend.llm import client as llm


# Keywords that indicate complex reasoning is needed
REASONING_SIGNALS = [
    "predict", "analyze", "why", "explain", "compare", "evaluate",
    "strategy", "risk", "scenario", "pressure point", "catalyst",
    "argue", "debate", "challenge", "flip", "disrupt", "collapse",
    "what if", "what would happen", "how could", "vulnerability",
]


def classify_complexity(prompt: str) -> str:
    """Determine if a prompt needs the reasoning model or cluster model.

    Returns 'reasoning' or 'cluster'.
    """
    prompt_lower = prompt.lower()

    # Check for reasoning signals
    signal_count = sum(1 for s in REASONING_SIGNALS if s in prompt_lower)

    # Long prompts with complex structure → reasoning
    if signal_count >= 2:
        return "reasoning"

    # Short prompts with simple asks → cluster (cheap model)
    if len(prompt) < 200 and signal_count == 0:
        return "cluster"

    # JSON formatting tasks → cluster
    if "json" in prompt_lower and signal_count < 2:
        return "cluster"

    # Default to reasoning for safety
    return "reasoning"


async def smart_chat(
    prompt: str,
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    json_mode: bool = False,
    force_model: str | None = None,
) -> tuple[str, str]:
    """Route to the optimal model automatically.

    Returns (response_text, model_used).
    """
    model = force_model or classify_complexity(prompt)

    response = await llm.chat(
        prompt=prompt,
        system=system,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=json_mode,
    )
    return response, model


async def smart_chat_stream(
    prompt: str,
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    force_model: str | None = None,
):
    """Stream route to optimal model. Yields text chunks."""
    model = force_model or classify_complexity(prompt)

    async for chunk in llm.chat_stream(
        prompt=prompt,
        system=system,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    ):
        yield chunk
