"""Central chat-model factory."""
from __future__ import annotations
from functools import lru_cache
from .config import get_settings
def _provider_extra() -> dict:
    s = get_settings()
    if s.llm_base_url:
        return {"base_url": s.llm_base_url, "api_key": s.llm_api_key or "lm-studio"}
    return {}
def chat_model(**kwargs):
    """Build the configured chat model (cloud, or local OpenAI-compatible)."""
    from langchain.chat_models import init_chat_model  # noqa: PLC0415
    s = get_settings()
    s.export_provider_env()
    return init_chat_model(s.model, **_provider_extra(), **kwargs)
@lru_cache
def shared_chat_model():
    """A process-wide shared instance (for the agent layer)."""
    return chat_model()
