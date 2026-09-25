"""
Hybrid retrieval: dense (HNSW via pgvector) + sparse (BM25 via tsvector),
fused with Reciprocal Rank Fusion (RRF), all in a SINGLE SQL query.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from models import get_embedder
from rag.query_rewrite import normalize_query

# Thread pool for CPU-bound embedding
_embed_executor = ThreadPoolExecutor(max_workers=2)


def _embed_sync(texts: list[str], normalize: bool = True) -> list[list[float]]:
    """Synchronous embedding in thread pool."""
    model = get_embedder()
    embeddings = model.encode(
        texts,
        normalize_embeddings=normalize,
        batch_size=16,
        show_progress_bar=False,
    )
    if len(texts) == 1:
        return [embeddings[0].tolist()]
    return embeddings.tolist()


async def embed_query(q: str) -> list[float]:
    """Encode a user query with BGE-M3 (dense) - async wrapper."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_embed_executor, _embed_sync, [q], True)
    return result[0]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch encode texts with BGE-M3 (dense) - async wrapper."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_embed_executor, _embed_sync, texts, True)


HYBRID_SQL = sql_text("""
WITH dense AS (
    SELECT c.id,
           ROW_NUMBER() OVER (
             ORDER BY c.embedding <=> CAST(:vec AS vector)
           ) AS rank,
           1 - (c.embedding <=> CAST(:vec AS vector)) AS score
    FROM chunks c
    WHERE c.tenant_id = :tenant_id
      AND c.embedding IS NOT NULL
    ORDER BY c.embedding <=> CAST(:vec AS vector)
    LIMIT :dense_k
),
sparse AS (
    SELECT c.id,
           ROW_NUMBER() OVER (
             ORDER BY ts_rank_cd(
               to_tsvector('english', c.text),
               plainto_tsquery('english', :q)
             ) DESC
           ) AS rank,
           ts_rank_cd(
             to_tsvector('english', c.text),
             plainto_tsquery('english', :q)
           ) AS score
    FROM chunks c
    WHERE c.tenant_id = :tenant_id
      AND to_tsvector('english', c.text) @@ plainto_tsquery('english', :q)
    ORDER BY ts_rank_cd(
      to_tsvector('english', c.text),
      plainto_tsquery('english', :q)
    ) DESC
    LIMIT :sparse_k
),
fused AS (
    SELECT
      COALESCE(d.id, s.id) AS id,
      COALESCE(1.0 / (:rrf_k + d.rank), 0) +
      COALESCE(1.0 / (:rrf_k + s.rank), 0) AS rrf_score,
      d.score AS dense_score,
      s.score AS sparse_score
    FROM dense d
    FULL OUTER JOIN sparse s ON s.id = d.id
)
SELECT
  f.id, f.rrf_score, f.dense_score, f.sparse_score,
  c.text, c.document_id, c.page_number, c.heading_path,
  d.title, d.filename, d.url
FROM fused f
JOIN chunks c ON c.id = f.id
JOIN documents d ON d.id = c.document_id
WHERE d.status = 'active'
ORDER BY f.rrf_score DESC
LIMIT :k
""")


async def hybrid_retrieve(
    query: str,
    tenant_id: str,
    db: AsyncSession,
    k: int = 20,
) -> list[dict]:
    # Normalize Hinglish -> English so English docs match Hinglish queries
    search_query = normalize_query(query)
    vec = await embed_query(search_query)

    # Higher ef_search = better recall (slight latency cost)
    await db.execute(
        sql_text(f"SET LOCAL hnsw.ef_search = {settings.HNSW_EF_SEARCH}")
    )

    rows = (await db.execute(HYBRID_SQL, {
        "vec": str(vec),
        "q": search_query,
        "tenant_id": tenant_id,
        "dense_k": settings.TOP_K_DENSE,
        "sparse_k": settings.TOP_K_SPARSE,
        "rrf_k": settings.RRF_K,
        "k": k,
    })).mappings().all()

    return [
        {
            "chunk_id": str(r["id"]),
            "document_id": str(r["document_id"]),
            "text": r["text"],
            "title": r["title"] or r["filename"],
            "url": r["url"],
            "source": r["filename"],
            "page_number": r["page_number"],
            "heading_path": r["heading_path"],
            "dense_score": float(r["dense_score"] or 0),
            "sparse_score": float(r["sparse_score"] or 0),
            "score": float(r["rrf_score"]),
        }
        for r in rows
    ]