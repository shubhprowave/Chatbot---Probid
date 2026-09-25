from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
import json, time, logging, asyncio

from db.postgres import AsyncSessionLocal
from db.models import Conversation, Message
from db.redis_client import cache_set
from rag.pipeline import rag_pipeline

router = APIRouter()
log = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default="anon", max_length=128)
    tenant_id: str = Field(default="default", max_length=64)
    history: list[dict] = Field(default_factory=list)


async def _ensure_conversation(session_id: str, tenant_id: str, request: Request) -> str:
    async with AsyncSessionLocal() as db:
        conv = (await db.execute(
            select(Conversation).where(
                Conversation.session_id == session_id,
                Conversation.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if conv:
            return str(conv.id)
        conv = Conversation(
            tenant_id=tenant_id,
            session_id=session_id,
            user_ip=request.client.host if request.client else None,
            user_agent=(request.headers.get("user-agent") or "")[:500],
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return str(conv.id)


async def _save_user_message(conversation_id: str, content: str):
    async with AsyncSessionLocal() as db:
        db.add(Message(
            conversation_id=conversation_id,
            role="user",
            content=content,
        ))
        await db.commit()


async def _save_assistant_message(
    conversation_id: str,
    content: str,
    sources: list,
    model: str | None,
    latency_ms: int,
    cache_hit: bool,
):
    async with AsyncSessionLocal() as db:
        db.add(Message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            sources=sources,
            model=model,
            latency_ms=latency_ms,
            cache_hit=cache_hit,
        ))
        await db.commit()


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    t0 = time.perf_counter()

    conversation_id = await _ensure_conversation(
        req.session_id, req.tenant_id, request
    )
    await _save_user_message(conversation_id, req.question)

    async def event_stream():
        # Send immediate acknowledgment to show chatbot is working
        init = {"type": "init", "status": "processing"}
        yield f"data: {json.dumps(init)}\n\n"
        yield ": ping\n\n"
        await asyncio.sleep(0)

        # Run RAG pipeline
        async with AsyncSessionLocal() as rag_db:
            result = await rag_pipeline(
                req.question, req.history, req.tenant_id, rag_db
            )

        # Send metadata as soon as available
        meta = {
            "type": "meta",
            "sources": result["sources"],
            "tenders": result.get("tenders") or [],
            "latency_ms": result["latency_ms"],
            "cached": result["cached"],
        }
        yield f"data: {json.dumps(meta)}\n\n"
        yield ": ping\n\n"
        await asyncio.sleep(0)

        # Stream tokens one by one
        collected: list[str] = []
        try:
            async for token in result["answer_gen"]:
                collected.append(token)
                frame = json.dumps({"type": "token", "data": token})
                yield f"data: {frame}\n\n"
                # Tiny yield so the loop stays async without throttling the stream
                await asyncio.sleep(0.001)
        except Exception as e:
            log.exception(f"[stream] token error: {e}")

        full_answer = "".join(collected)
        total_ms = int((time.perf_counter() - t0) * 1000)

        try:
            await _save_assistant_message(
                conversation_id=conversation_id,
                content=full_answer,
                sources=result["sources"],
                model=result.get("model"),
                latency_ms=total_ms,
                cache_hit=result.get("cached", False),
            )
        except Exception as e:
            log.exception(f"[save] assistant message failed: {e}")

        if not result.get("cached") and "cache_key" in result:
            try:
                await cache_set(result["cache_key"], {
                    "answer": full_answer,
                    "sources": result["sources"],
                    "model": result.get("model"),
                })
            except Exception as e:
                log.exception(f"[cache] save failed: {e}")

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "identity",   # disable gzip
        },
    )