from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile, File, Form
from sqlalchemy import select, func, desc, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession
from db.postgres import get_db
from db.models import Document, Chunk, Conversation, Message, Feedback, Unanswered
from config import settings
from analytics import queries as q
from analytics.cost import cost_summary
import uuid
import httpx

router = APIRouter(prefix="/admin")


def require_admin(authorization: str = Header(None)):
    if authorization != f"Bearer {settings.ADMIN_TOKEN}":
        raise HTTPException(401, "unauthorized")


@router.get("/stats", dependencies=[Depends(require_admin)])
async def stats(
    tenant_id: str = "default",
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
):
    return await q.overview_stats(db, tenant_id, hours)


@router.get("/documents", dependencies=[Depends(require_admin)])
async def list_docs(
    tenant_id: str = "default",
    limit: int = 500,
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Document).where(Document.tenant_id == tenant_id)
        .order_by(desc(Document.created_at)).limit(limit)
    )).scalars().all()

    # Count chunks per doc in one query
    doc_ids = [d.id for d in rows]
    counts = {}
    if doc_ids:
        c_rows = (await db.execute(sql_text(
            "SELECT document_id, COUNT(*) AS c FROM chunks WHERE document_id = ANY(:ids) GROUP BY document_id"
        ), {"ids": doc_ids})).mappings().all()
        counts = {str(r["document_id"]): int(r["c"]) for r in c_rows}

    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "title": d.title,
            "source_type": d.source_type,
            "status": d.status,
            "size_bytes": d.size_bytes,
            "chunk_count": counts.get(str(d.id), 0),
            "chunk_strategy": (d.doc_metadata or {}).get("chunking", {}).get("strategy"),
            "chunk_params": (d.doc_metadata or {}).get("chunking", {}).get("params"),
            "created_at": d.created_at.isoformat(),
        }
        for d in rows
    ]


@router.post("/documents/upload", dependencies=[Depends(require_admin)])
async def upload_doc(
    files: list[UploadFile] = File(...),
    tenant_id: str = Form("default"),
    chunk_strategy: str = Form("auto"),
    chunk_params: str = Form("{}"),
    db: AsyncSession = Depends(get_db),
):
    """Delegates to /ingest with same behavior."""
    from api.ingest import ingest
    return await ingest(
        files=files,
        tenant_id=tenant_id,
        chunk_strategy=chunk_strategy,
        chunk_params=chunk_params,
        authorization=f"Bearer {settings.ADMIN_TOKEN}",
        db=db,
    )


@router.get("/chunking/strategies", dependencies=[Depends(require_admin)])
async def chunking_strategies():
    """Available chunking strategies + param schemas (drives the UI form)."""
    from ingestion.chunker import list_strategies
    return {"strategies": list_strategies()}


@router.post("/documents/create-text", dependencies=[Depends(require_admin)])
async def create_text_document(
    title: str = Form(...),
    text: str = Form(...),
    tenant_id: str = Form("default"),
    chunk_strategy: str = Form("auto"),
    chunk_params: str = Form("{}"),
    db: AsyncSession = Depends(get_db),
):
    """Create a document directly from text without file upload."""
    from ingestion.chunker import chunk_document
    from rag.retriever import embed_texts
    import uuid
    import hashlib
    import json

    try:
        params = json.loads(chunk_params or "{}")
        if not isinstance(params, dict):
            params = {}
    except json.JSONDecodeError:
        raise HTTPException(400, "chunk_params must be valid JSON")

    # Create file hash from text content
    file_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()

    # Create document
    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        filename=f"{title}.txt",
        file_hash=file_hash,
        mime_type="text/plain",
        title=title,
        source_type="text",
        status="processing",
        size_bytes=len(text.encode('utf-8')),
        doc_metadata={},
    )
    db.add(doc)
    await db.flush()

    try:
        # Chunk the text with the chosen strategy
        metadata = {"title": title, "source_type": "text"}
        result = chunk_document(
            text,
            strategy=chunk_strategy,
            params=params,
            metadata=metadata,
            filename=f"{title}.txt",
        )

        chunks_data = result["chunks"]
        resolved_strategy = result["strategy"]
        used_params = result["params"]

        if not chunks_data:
            doc.status = "failed"
            await db.commit()
            raise HTTPException(400, "No chunks created from text")

        doc.doc_metadata = {
            "chunking": {"strategy": resolved_strategy, "params": used_params}
        }

        # Create chunks
        chunk_objs = []
        for chunk_data in chunks_data:
            chunk_objs.append(Chunk(
                id=uuid.uuid4(),
                document_id=doc.id,
                tenant_id=tenant_id,
                chunk_index=chunk_data["chunk_index"],
                text=chunk_data["text"],
                char_count=chunk_data["char_count"],
                heading_path=None,
                chunk_metadata={"chunk_strategy": resolved_strategy},
            ))

        db.add_all(chunk_objs)
        await db.flush()

        # Embed in batches
        BATCH = 16
        for i in range(0, len(chunk_objs), BATCH):
            batch = chunk_objs[i:i + BATCH]
            vecs = await embed_texts([c.text for c in batch])
            for c, v in zip(batch, vecs):
                c.embedding = v

        doc.status = "active"
        await db.commit()

        return {
            "status": "created",
            "document_id": str(doc.id),
            "chunks": len(chunk_objs),
            "strategy": resolved_strategy,
        }

    except Exception as e:
        doc.status = "failed"
        await db.commit()
        raise HTTPException(500, f"Failed to create document: {str(e)}")


@router.delete("/documents/{doc_id}", dependencies=[Depends(require_admin)])
async def delete_doc(doc_id: str, db: AsyncSession = Depends(get_db)):
    doc = (await db.execute(
        select(Document).where(Document.id == uuid.UUID(doc_id))
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "not found")
    await db.delete(doc)
    await db.commit()
    return {"status": "deleted"}


@router.get("/documents/{doc_id}/chunks", dependencies=[Depends(require_admin)])
async def doc_chunks(doc_id: str, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(Chunk).where(Chunk.document_id == uuid.UUID(doc_id))
        .order_by(Chunk.chunk_index).limit(500)
    )).scalars().all()
    return [
        {
            "id": str(c.id),
            "chunk_index": c.chunk_index,
            "text": c.text,
            "char_count": c.char_count,
            "has_embedding": c.embedding is not None,
        } for c in rows
    ]


@router.put("/chunks/{chunk_id}", dependencies=[Depends(require_admin)])
async def update_chunk(
    chunk_id: str,
    text: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Update chunk text and re-embed it."""
    from rag.retriever import embed_texts
    
    chunk = (await db.execute(
        select(Chunk).where(Chunk.id == uuid.UUID(chunk_id))
    )).scalar_one_or_none()
    
    if not chunk:
        raise HTTPException(404, "Chunk not found")
    
    # Update text
    chunk.text = text
    chunk.char_count = len(text)
    
    # Re-embed
    try:
        vecs = await embed_texts([text])
        chunk.embedding = vecs[0]
        await db.commit()
        
        return {
            "status": "updated",
            "chunk_id": str(chunk.id),
            "char_count": chunk.char_count
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(500, f"Failed to update chunk: {str(e)}")


@router.delete("/chunks/{chunk_id}", dependencies=[Depends(require_admin)])
async def delete_chunk(chunk_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a specific chunk."""
    chunk = (await db.execute(
        select(Chunk).where(Chunk.id == uuid.UUID(chunk_id))
    )).scalar_one_or_none()
    
    if not chunk:
        raise HTTPException(404, "Chunk not found")
    
    await db.delete(chunk)
    await db.commit()
    
    return {"status": "deleted", "chunk_id": str(chunk_id)}


@router.post("/documents/{doc_id}/reembed", dependencies=[Depends(require_admin)])
async def reembed_doc(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Re-generate embeddings for a document (after model change)."""
    from rag.retriever import embed_texts
    chunks = (await db.execute(
        select(Chunk).where(Chunk.document_id == uuid.UUID(doc_id))
    )).scalars().all()
    if not chunks:
        raise HTTPException(404, "no chunks")
    BATCH = 16
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        vecs = await embed_texts([c.text for c in batch])
        for c, v in zip(batch, vecs):
            c.embedding = v
        await db.commit()
    return {"status": "reembedded", "chunks": len(chunks)}


@router.get("/conversations", dependencies=[Depends(require_admin)])
async def conversations(
    tenant_id: str = "default",
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    return await q.recent_conversations(db, tenant_id, limit)


@router.get("/conversations/{conversation_id}", dependencies=[Depends(require_admin)])
async def conversation_detail(conversation_id: str, db: AsyncSession = Depends(get_db)):
    return await q.conversation_detail(db, conversation_id)


@router.get("/unanswered", dependencies=[Depends(require_admin)])
async def unanswered(tenant_id: str = "default", limit: int = 100,
                     db: AsyncSession = Depends(get_db)):
    return await q.unanswered_questions(db, tenant_id, limit)


@router.get("/feedback/recent", dependencies=[Depends(require_admin)])
async def feedback_recent(db: AsyncSession = Depends(get_db), limit: int = 50):
    q = sql_text("""
    SELECT f.id, f.rating, f.comment, f.created_at,
           m.content AS answer,
           (SELECT content FROM messages m2
            WHERE m2.conversation_id = m.conversation_id AND m2.role = 'user'
            ORDER BY m2.created_at DESC LIMIT 1) AS question
    FROM feedback f
    JOIN messages m ON m.id = f.message_id
    ORDER BY f.created_at DESC LIMIT :limit;
    """)
    rows = (await db.execute(q, {"limit": limit})).mappings().all()
    return [
        {
            "id": str(r["id"]),
            "rating": r["rating"],
            "comment": r["comment"],
            "question": r["question"],
            "answer": r["answer"],
            "created_at": r["created_at"].isoformat(),
        } for r in rows
    ]


@router.get("/cost", dependencies=[Depends(require_admin)])
async def cost(tenant_id: str = "default", days: int = 30,
               db: AsyncSession = Depends(get_db)):
    return await cost_summary(db, tenant_id, days)


@router.get("/storage", dependencies=[Depends(require_admin)])
async def storage_usage(
    tenant_id: str = "default",
    db: AsyncSession = Depends(get_db),
):
    """Estimates on-disk storage for source files, chunk text, and vector
    embeddings. Embedding size = 1024 float32 components (4096 bytes each)."""
    files_row = (await db.execute(sql_text(
        "SELECT COALESCE(SUM(size_bytes), 0) AS total FROM documents "
        "WHERE tenant_id = :t"
    ), {"t": tenant_id})).mappings().first()

    chunks_row = (await db.execute(sql_text(
        "SELECT COALESCE(SUM(octet_length(text)), 0) AS text_total, "
        "COUNT(*) AS n_total, "
        "COUNT(embedding) AS n_embedded FROM chunks "
        "WHERE tenant_id = :t"
    ), {"t": tenant_id})).mappings().first()

    embed_dim = 1024
    files_bytes = int(files_row["total"]) if files_row else 0
    chunks_bytes = int(chunks_row["text_total"]) if chunks_row else 0
    n_total = int(chunks_row["n_total"]) if chunks_row else 0
    n_embedded = int(chunks_row["n_embedded"]) if chunks_row else 0
    embeddings_bytes = n_embedded * embed_dim * 4  # float32

    total = files_bytes + chunks_bytes + embeddings_bytes

    return {
        "files_bytes": files_bytes,
        "chunks_bytes": chunks_bytes,
        "embeddings_bytes": embeddings_bytes,
        "total_bytes": total,
        "chunk_count": n_total,
        "embedding_count": n_embedded,
        "embed_dim": embed_dim,
    }


@router.get("/users", dependencies=[Depends(require_admin)])
async def list_leads(
    tenant_id: str = "default",
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
):
    """List registered chatbot visitors (name + phone) for the sales team."""
    rows = (await db.execute(sql_text(
        """
        SELECT u.id, u.name, u.phone, u.session_id, u.last_seen, u.created_at,
               (SELECT COUNT(*) FROM messages m
                JOIN conversations c ON c.id = m.conversation_id
                WHERE c.session_id = u.session_id) AS message_count
        FROM users u
        WHERE u.tenant_id = :t
        ORDER BY u.created_at DESC
        LIMIT :limit
        """
    ), {"t": tenant_id, "limit": limit})).mappings().all()

    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "phone": r["phone"],
            "session_id": r["session_id"],
            "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "message_count": int(r["message_count"] or 0),
        }
        for r in rows
    ]


@router.get("/health", dependencies=[Depends(require_admin)])
async def system_health(db: AsyncSession = Depends(get_db)):
    from db.redis_client import r

    health = {"postgres": "unknown", "redis": "unknown", "llm": "unknown", "llm_error": None}

    try:
        await db.execute(sql_text("SELECT 1"))
        health["postgres"] = "ok"
    except Exception as e:
        health["postgres"] = "down"

    try:
        await r.ping()
        health["redis"] = "ok"
    except Exception as e:
        health["redis"] = "down"

    try:
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(
                f"{settings.LLM_BASE_URL.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            )
            health["llm"] = "ok" if resp.status_code == 200 else f"http {resp.status_code}"
    except Exception as e:
        health["llm"] = "down"
        health["llm_error"] = repr(e)

    return health


# =========================================================
# System Prompt Management
# =========================================================
@router.get("/prompt", dependencies=[Depends(require_admin)])
async def get_prompt():
    """Get the current system prompt."""
    from rag.generator import get_system_prompt
    return {"prompt": get_system_prompt()}


@router.put("/prompt", dependencies=[Depends(require_admin)])
async def update_prompt(prompt: str = Form(...)):
    """Update the system prompt."""
    from rag.generator import set_system_prompt
    
    if not prompt or len(prompt.strip()) < 10:
        raise HTTPException(400, "Prompt must be at least 10 characters")
    
    set_system_prompt(prompt.strip())
    return {"status": "updated", "prompt": prompt.strip()}


@router.post("/prompt/reset", dependencies=[Depends(require_admin)])
async def reset_prompt():
    """Restore the default system prompt."""
    from rag.generator import reset_system_prompt, get_system_prompt

    reset_system_prompt()
    return {"status": "updated", "prompt": get_system_prompt()}
