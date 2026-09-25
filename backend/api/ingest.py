from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.postgres import get_db
from db.models import Document, Chunk
from ingestion.loader import load_file
from ingestion.chunker import chunk_document
from rag.retriever import embed_texts
from config import settings
import hashlib
import json

router = APIRouter()

def _parse_chunk_params(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "chunk_params must be valid JSON")
    return data if isinstance(data, dict) else {}


@router.post("/ingest")
async def ingest(
    files: list[UploadFile] = File(...),
    tenant_id: str = Form("default"),
    chunk_strategy: str = Form("auto"),
    chunk_params: str = Form("{}"),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    if authorization != f"Bearer {settings.ADMIN_TOKEN}":
        raise HTTPException(401, "unauthorized")

    summary = []

    for f in files:
        raw = await f.read()
        file_hash = hashlib.sha256(raw).hexdigest()

        # Dedupe
        existing = (await db.execute(
            select(Document).where(
                Document.tenant_id == tenant_id,
                Document.file_hash == file_hash,
            )
        )).scalar_one_or_none()
        if existing:
            summary.append({"file": f.filename, "status": "duplicate_skipped",
                            "document_id": str(existing.id)})
            continue

        # Load + chunk
        try:
            text = load_file(f.filename, raw)
        except Exception as e:
            summary.append({"file": f.filename, "status": "parse_failed", "error": str(e)})
            continue

        try:
            chunk_params_data = _parse_chunk_params(chunk_params)
            result = chunk_document(
                text,
                strategy=chunk_strategy,
                params=chunk_params_data,
                metadata={"source": f.filename},
                filename=f.filename,
            )
        except ValueError as e:
            summary.append({"file": f.filename, "status": "chunk_failed", "error": str(e)})
            continue

        chunks_data = result["chunks"]
        resolved_strategy = result["strategy"]
        used_params = result["params"]
        if not chunks_data:
            summary.append({"file": f.filename, "status": "no_content"})
            continue

        # Insert document
        doc = Document(
            tenant_id=tenant_id,
            filename=f.filename,
            file_hash=file_hash,
            mime_type=f.content_type,
            size_bytes=len(raw),
            title=f.filename,
            source_type=f.filename.rsplit(".", 1)[-1].lower(),
            status="active",
            doc_metadata={"chunking": {"strategy": resolved_strategy, "params": used_params}},
        )
        db.add(doc)
        await db.flush()

        # Embed in batches + insert chunks
        BATCH = 16
        for i in range(0, len(chunks_data), BATCH):
            batch = chunks_data[i:i + BATCH]
            vectors = await embed_texts([c["text"] for c in batch])
            for j, (chunk, vec) in enumerate(zip(batch, vectors)):
                db.add(Chunk(
                    document_id=doc.id,
                    tenant_id=tenant_id,
                    chunk_index=chunk["chunk_index"],
                    text=chunk["text"],
                    char_count=chunk["char_count"],
                    chunk_metadata={
                        "source": f.filename,
                        "chunk_strategy": resolved_strategy,
                    },
                    embedding=vec,
                ))

        await db.commit()
        summary.append({
            "file": f.filename,
            "document_id": str(doc.id),
            "chunks": len(chunks_data),
            "strategy": resolved_strategy,
            "status": "ingested",
        })

    return {"results": summary}