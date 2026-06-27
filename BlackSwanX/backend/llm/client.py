"""Triple-model Ollama LLM client.

Three-model strategy for M2 Pro 16GB:
  - Swarm (llama3.2:3b): Fast, cheap citizen simulation. Biased humans.
  - Assassin (phi4:14b): Deep reasoning for kill shots and stress tests.
  - Nexus Brain (mistral-small:24b): Synthesis, DAG construction, elite analysis.

All calls go through Ollama's native API (not OpenAI-compat, for keep_alive control).
"""
import httpx
import json
from typing import AsyncGenerator
from backend.config import settings
from backend.hardware import detect_hardware, ASSASSIN_MODEL

_hardware = None
_swarm_model = None
_reasoning_model = None
_assassin_model = ASSASSIN_MODEL


def _init_models():
    global _hardware, _swarm_model, _reasoning_model
    if _hardware is None:
        _hardware = detect_hardware()
        _swarm_model = settings.cluster_model or _hardware.recommended_cluster_model
        _reasoning_model = settings.reasoning_model or _hardware.recommended_reasoning_model


def get_models() -> dict:
    _init_models()
    return {
        "swarm": _swarm_model,
        "assassin": _assassin_model,
        "nexus": _reasoning_model,
    }


def _resolve_model(model: str) -> str:
    """Resolve model alias to actual model name."""
    _init_models()
    mapping = {
        "cluster": _swarm_model,
        "swarm": _swarm_model,
        "assassin": _assassin_model,
        "reasoning": _reasoning_model,
        "nexus": _reasoning_model,
        "elite": _reasoning_model,
    }
    return mapping.get(model, _reasoning_model)


async def chat(
    prompt: str,
    system: str = "",
    model: str = "reasoning",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    json_mode: bool = False,
) -> str:
    """Send a chat completion request to Ollama. Returns full response."""
    _init_models()
    model_name = _resolve_model(model)
    base = settings.ollama_base_url

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens:
        body["options"] = {"num_predict": max_tokens}
    if json_mode:
        body["format"] = "json"

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(f"{base}/api/chat", json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]


async def chat_stream(
    prompt: str,
    system: str = "",
    model: str = "reasoning",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    """Stream a chat completion from Ollama. Yields text chunks."""
    _init_models()
    model_name = _resolve_model(model)
    base = settings.ollama_base_url

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if max_tokens:
        body["options"] = {"num_predict": max_tokens}

    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream("POST", f"{base}/api/chat", json=body) as resp:
            async for line in resp.aiter_lines():
                if line.strip():
                    chunk = json.loads(line)
                    if content := chunk.get("message", {}).get("content", ""):
                        yield content


async def flush_gpu_cache(model: str = "cluster"):
    """Flush Ollama model from RAM. Essential for M2 Pro stability between swarm waves.

    Uses keep_alive: 0 to force immediate unload.
    """
    _init_models()
    model_name = _resolve_model(model)
    base = settings.ollama_base_url

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(f"{base}/api/generate", json={
                "model": model_name,
                "prompt": "",
                "keep_alive": 0,
            })
    except Exception:
        pass  # Non-critical — just a RAM optimization


async def embed(texts: list[str], model: str = "swarm") -> list[list[float]]:
    """Get embeddings from Ollama. Uses the swarm model (small/fast)."""
    _init_models()
    model_name = _resolve_model(model)
    base = settings.ollama_base_url

    embeddings = []
    async with httpx.AsyncClient(timeout=120) as client:
        for text in texts:
            resp = await client.post(
                f"{base}/api/embed",
                json={"model": model_name, "input": text}
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings.append(data["embeddings"][0])
    return embeddings
