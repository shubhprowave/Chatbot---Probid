"""
Re-embed all chunks with the current embedding model.
Use when: switching EMBEDDING_MODEL, fixing bad vectors, or recovering.
"""
import asyncio
from sqlalchemy import select
from db.postgres import AsyncSessionLocal
from db.models import Chunk
from rag.retriever import embed_texts


async def main():
    async with AsyncSessionLocal() as db:
        chunks = (await db.execute(select(Chunk).order_by(Chunk.created_at))).scalars().all()
        print(f"Re-embedding {len(chunks)} chunks...")

        BATCH = 16
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i:i + BATCH]
            vecs = await embed_texts([c.text for c in batch])
            for c, v in zip(batch, vecs):
                c.embedding = v
            await db.commit()
            print(f"  {i + len(batch)}/{len(chunks)}")

        print("✅ Done")


if __name__ == "__main__":
    asyncio.run(main())