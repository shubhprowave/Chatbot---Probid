import asyncio
from concurrent.futures import ThreadPoolExecutor
from models import get_reranker
from config import settings

# Thread pool for CPU-bound reranking
_executor = ThreadPoolExecutor(max_workers=2)


def _rerank_sync(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    """Synchronous reranking in thread pool."""
    reranker = get_reranker()
    pairs = [(query, c["text"][:512]) for c in chunks]  # Limit text length
    scores = reranker.predict(pairs, batch_size=16, show_progress_bar=False)
    
    ranked = sorted(zip(chunks, scores), key=lambda x: float(x[1]), reverse=True)
    return [
        {**c, "rerank_score": float(s)}
        for c, s in ranked[:top_k]
    ]


async def rerank(query: str, chunks: list[dict], top_k: int | None = None) -> list[dict]:
    """Cross-encoder reranking with BGE-reranker-base (async wrapper)."""
    if not chunks:
        return []
    top_k = top_k or settings.TOP_K_RERANK
    
    # Run in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _rerank_sync, query, chunks, top_k)