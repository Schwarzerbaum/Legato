"""Chat endpoints — interact with simulated agents post-simulation."""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.llm import client as llm
from backend.llm.prompts import PROVOCATEUR_SYSTEM, WHALE_SYSTEM, CATALYST_SYSTEM

router = APIRouter()

AGENT_PROMPTS = {
    "provocateur": PROVOCATEUR_SYSTEM,
    "whale": WHALE_SYSTEM,
    "catalyst": CATALYST_SYSTEM,
}


class ChatRequest(BaseModel):
    agent: str  # provocateur, whale, catalyst
    message: str
    context: str = ""  # Optional simulation context


@router.post("/message")
async def chat_with_agent(req: ChatRequest):
    """Chat with a simulated agent. Returns streaming markdown."""
    system = AGENT_PROMPTS.get(req.agent, "You are a helpful analyst.")

    if req.context:
        system += f"\n\nSimulation Context:\n{req.context}"

    prompt = req.message

    async def stream():
        async for chunk in llm.chat_stream(prompt=prompt, system=system):
            yield chunk

    return StreamingResponse(stream(), media_type="text/plain")
