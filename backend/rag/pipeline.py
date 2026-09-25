import time
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from rag.retriever import hybrid_retrieve
from rag.reranker import rerank
from rag.generator import generate_answer, wants_contact, answer_contact
from db.redis_client import cache_get, cache_set, make_cache_key
from tenders.text_to_sql import (
    is_tender_query,
    answer_tender_query,
    looks_like_sql,
    build_sql_rejection,
)

log = logging.getLogger(__name__)


async def rag_pipeline(
    question: str,
    history: list,
    tenant_id: str,
    db: AsyncSession,
):
    t0 = time.perf_counter()

    # Reject raw SQL / injection-style input — only plain-language questions allowed
    if looks_like_sql(question):
        log.warning("[guard] blocked raw SQL input: %.120r", question)
        return {
            "answer_gen": _stream_from_text(build_sql_rejection(question)),
            "sources": [],
            "model": None,
            "kind": "BLOCKED",
            "cached": False,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }

    # 0. Cache
    cache_key = make_cache_key(question, tenant_id)
    if cached := await cache_get(cache_key):
        return {
            "answer_gen": _stream_from_text(cached["answer"]),
            "sources": cached["sources"],
            "model": cached.get("model"),
            "cached": True,
            "latency_ms": 0,
        }

    # Contact short-circuit: phone/mobile/email questions are answered
    # deterministically from the official contact block — no retrieval/LLM,
    # so the number is ALWAYS given (even with typos like "moblie").
    if wants_contact(question):
        log.info("[contact] deterministic contact answer for: %.80r", question)
        return {
            "answer_gen": _stream_from_text(answer_contact(question)),
            "sources": [],
            "model": None,
            "kind": "CONTACT",
            "cached": False,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "cache_key": cache_key,
        }

    # Check if this is a greeting or simple general question
    question_lower = question.lower().strip()
    greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'hola', 'namaste', 
                 'नमस्ते', 'हाय', 'हेलो', 'प्रणाम', 'हैलो']
    simple_questions = ['what is this', 'what are you', 'who are you', 'how can you help', 'what do you do',
                       'यह क्या है', 'आप कौन हैं', 'आप क्या करते हैं', 'मदद']
    
    is_greeting = any(question_lower == g or question_lower.startswith(g + ' ') or question_lower.startswith(g + ',') for g in greetings)
    is_simple = any(q in question_lower for q in simple_questions) and len(question.split()) < 10
    
    # For greetings and simple questions, skip retrieval
    if is_greeting or is_simple:
        answer_gen, sources, used_model = await generate_answer(
            question, [], history, settings.LLM_MODEL
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "answer_gen": answer_gen,
            "sources": [],  # No sources for greetings
            "model": used_model,
            "kind": "SIMPLE",
            "cached": False,
            "latency_ms": latency_ms,
            "cache_key": cache_key,
        }

    # Tender database path: natural language -> SQL over MySQL (live + fresh)
    if settings.TENDER_ENABLED and await is_tender_query(question):
        try:
            result = await answer_tender_query(question, history)
            result["latency_ms"] = int((time.perf_counter() - t0) * 1000)
            return result
        except Exception as e:
            log.exception("[tender] query failed, tender DB unavailable: %s", e)
            return {
                "answer_gen": _stream_from_text(_tender_unavailable(question)),
                "sources": [],
                "tenders": [],
                "model": None,
                "kind": "TENDER_ERROR",
                "cached": False,
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            }

    # 1. Hybrid retrieval (dense + BM25 RRF) — single query
    # Retrieve from PostgreSQL database only
    chunks = await hybrid_retrieve(question, tenant_id, db, k=settings.TOP_K_HYBRID)

    # 2. Fast rerank with smaller batch - run in background if needed
    # Only rerank if we have more chunks than needed
    if len(chunks) > settings.TOP_K_RERANK:
        top = await rerank(question, chunks, top_k=settings.TOP_K_RERANK)
    else:
        top = chunks

    # 3. Generate - streaming starts immediately
    answer_gen, sources, used_model = await generate_answer(
        question, top, history, settings.LLM_MODEL
    )

    latency_ms = int((time.perf_counter() - t0) * 1000)

    return {
        "answer_gen": answer_gen,
        "sources": sources,
        "model": used_model,
        "kind": "COMPLEX",
        "cached": False,
        "latency_ms": latency_ms,
        "cache_key": cache_key,
    }


async def _stream_from_text(text: str):
    for token in text.split(" "):
        yield token + " "


_TENDER_UNAVAILABLE = {
    "english": "I couldn't fetch live tender data right now — the tender database is temporarily unavailable. Please try again in a moment.",
    "hinglish": "Abhi live tender data nahi mil paya — tender database abhi temporarily unavailable hai. Kripya thodi der baad dobara try karein.",
    "hindi": "अभी लाइव टेंडर डेटा नहीं मिल पाया — टेंडर डेटाबेस अस्थायी रूप से उपलब्ध नहीं है। कृपया थोड़ी देर बाद फिर से कोशिश करें।",
}


def _tender_unavailable(question: str) -> str:
    from rag.generator import detect_language

    lang = detect_language(question) if question else "english"
    return _TENDER_UNAVAILABLE.get(lang, _TENDER_UNAVAILABLE["english"])