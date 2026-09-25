"""
All dashboard SQL queries. Pure SQL — fast, cacheable.
"""
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession


async def overview_stats(db: AsyncSession, tenant_id: str = "default", hours: int = 24) -> dict:
    q = sql_text("""
    WITH time_window AS (
      SELECT NOW() - INTERVAL '1 hour' * :hours AS since
    ),
    users AS (
      SELECT COUNT(DISTINCT c.session_id) AS unique_users
      FROM conversations c, time_window
      WHERE c.tenant_id = :tenant_id AND c.created_at >= time_window.since
    ),
    msgs AS (
      SELECT
        COUNT(*) FILTER (WHERE m.role = 'user') AS questions,
        COUNT(*) FILTER (WHERE m.role = 'assistant') AS answers,
        AVG(m.latency_ms) FILTER (WHERE m.role = 'assistant') AS avg_latency,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY m.latency_ms)
          FILTER (WHERE m.role = 'assistant') AS p50,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY m.latency_ms)
          FILTER (WHERE m.role = 'assistant') AS p95,
        AVG(m.cache_hit::int) FILTER (WHERE m.role = 'assistant') AS cache_rate,
        SUM(m.cost_usd) AS total_cost
      FROM messages m
      JOIN conversations c ON c.id = m.conversation_id, time_window
      WHERE c.tenant_id = :tenant_id AND m.created_at >= time_window.since
    ),
    docs AS (
      SELECT COUNT(*) AS doc_count FROM documents
      WHERE tenant_id = :tenant_id AND status = 'active'
    ),
    chunks AS (
      SELECT COUNT(*) AS chunk_count FROM chunks WHERE tenant_id = :tenant_id
    ),
    feedback AS (
      SELECT
        COUNT(*) FILTER (WHERE rating = 1) AS pos,
        COUNT(*) FILTER (WHERE rating = -1) AS neg
      FROM feedback f
      JOIN messages m ON m.id = f.message_id
      JOIN conversations c ON c.id = m.conversation_id, time_window
      WHERE c.tenant_id = :tenant_id AND f.created_at >= time_window.since
    )
    SELECT * FROM users, msgs, docs, chunks, feedback;
    """)
    row = (await db.execute(q, {"tenant_id": tenant_id, "hours": hours})).mappings().one()
    total_fb = (row["pos"] or 0) + (row["neg"] or 0)
    return {
        "unique_users": int(row["unique_users"] or 0),
        "questions": int(row["questions"] or 0),
        "answers": int(row["answers"] or 0),
        "avg_latency_ms": int(row["avg_latency"] or 0),
        "p50_latency_ms": int(row["p50"] or 0),
        "p95_latency_ms": int(row["p95"] or 0),
        "cache_hit_rate": float(row["cache_rate"] or 0),
        "total_cost_usd": float(row["total_cost"] or 0),
        "doc_count": int(row["doc_count"] or 0),
        "chunk_count": int(row["chunk_count"] or 0),
        "feedback_positive": int(row["pos"] or 0),
        "feedback_negative": int(row["neg"] or 0),
        "satisfaction": (row["pos"] / total_fb) if total_fb else None,
    }


async def timeseries(db: AsyncSession, tenant_id: str, hours: int = 24, bucket: str = "hour") -> dict:
    assert bucket in ("hour", "day")
    q = sql_text(f"""
    SELECT
      date_trunc('{bucket}', m.created_at) AS ts,
      COUNT(DISTINCT c.session_id) AS users,
      COUNT(*) FILTER (WHERE m.role = 'user') AS questions,
      AVG(m.latency_ms) FILTER (WHERE m.role = 'assistant') AS avg_latency,
      AVG(m.cache_hit::int) FILTER (WHERE m.role = 'assistant') AS cache_rate
    FROM messages m
    JOIN conversations c ON c.id = m.conversation_id
    WHERE c.tenant_id = :tenant_id
      AND m.created_at >= NOW() - INTERVAL '1 hour' * :hours
    GROUP BY ts ORDER BY ts;
    """)
    rows = (await db.execute(q, {"tenant_id": tenant_id, "hours": hours})).mappings().all()
    return {
        "timestamps": [r["ts"].isoformat() for r in rows],
        "users": [int(r["users"] or 0) for r in rows],
        "questions": [int(r["questions"] or 0) for r in rows],
        "avg_latency": [int(r["avg_latency"] or 0) for r in rows],
        "cache_rate": [float(r["cache_rate"] or 0) for r in rows],
    }


async def latency_histogram(db: AsyncSession, tenant_id: str, hours: int = 24) -> dict:
    q = sql_text("""
    SELECT
      width_bucket(latency_ms, 0, 60000, 12) AS bucket,
      COUNT(*) AS count,
      MIN(latency_ms) AS lo,
      MAX(latency_ms) AS hi
    FROM messages m
    JOIN conversations c ON c.id = m.conversation_id
    WHERE c.tenant_id = :tenant_id
      AND m.role = 'assistant'
      AND m.latency_ms IS NOT NULL
      AND m.created_at >= NOW() - INTERVAL '1 hour' * :hours
    GROUP BY bucket ORDER BY bucket;
    """)
    rows = (await db.execute(q, {"tenant_id": tenant_id, "hours": hours})).mappings().all()
    return {
        "buckets": [
            {"range_ms": [int(r["lo"]), int(r["hi"])], "count": int(r["count"])}
            for r in rows
        ]
    }


async def top_questions(db: AsyncSession, tenant_id: str, limit: int = 20) -> list[dict]:
    q = sql_text("""
    SELECT LOWER(TRIM(m.content)) AS q, COUNT(*) AS cnt
    FROM messages m
    JOIN conversations c ON c.id = m.conversation_id
    WHERE c.tenant_id = :tenant_id AND m.role = 'user'
      AND m.created_at >= NOW() - INTERVAL '7 days'
    GROUP BY q ORDER BY cnt DESC LIMIT :limit;
    """)
    rows = (await db.execute(q, {"tenant_id": tenant_id, "limit": limit})).mappings().all()
    return [{"question": r["q"], "count": int(r["cnt"])} for r in rows]


async def unanswered_questions(db: AsyncSession, tenant_id: str, limit: int = 50) -> list[dict]:
    q = sql_text("""
    SELECT question, top_score, created_at
    FROM unanswered
    WHERE tenant_id = :tenant_id
    ORDER BY created_at DESC LIMIT :limit;
    """)
    rows = (await db.execute(q, {"tenant_id": tenant_id, "limit": limit})).mappings().all()
    return [
        {"question": r["question"], "score": r["top_score"],
         "at": r["created_at"].isoformat()}
        for r in rows
    ]


async def recent_conversations(db: AsyncSession, tenant_id: str, limit: int = 50) -> list[dict]:
    q = sql_text("""
    SELECT
      c.id, c.session_id, c.created_at,
      COUNT(m.id) FILTER (WHERE m.role = 'user') AS question_count,
      MAX(m.created_at) AS last_message_at,
      (SELECT content FROM messages WHERE conversation_id = c.id AND role = 'user'
       ORDER BY created_at ASC LIMIT 1) AS first_question
    FROM conversations c
    LEFT JOIN messages m ON m.conversation_id = c.id
    WHERE c.tenant_id = :tenant_id
    GROUP BY c.id
    ORDER BY last_message_at DESC NULLS LAST
    LIMIT :limit;
    """)
    rows = (await db.execute(q, {"tenant_id": tenant_id, "limit": limit})).mappings().all()
    return [
        {
            "id": str(r["id"]),
            "session_id": r["session_id"],
            "created_at": r["created_at"].isoformat(),
            "question_count": int(r["question_count"] or 0),
            "last_message_at": r["last_message_at"].isoformat() if r["last_message_at"] else None,
            "first_question": r["first_question"],
        }
        for r in rows
    ]


async def conversation_detail(db: AsyncSession, conversation_id: str) -> dict:
    import uuid
    cid = uuid.UUID(conversation_id)
    conv = (await db.execute(sql_text(
        "SELECT id, session_id, user_ip, user_agent, created_at FROM conversations WHERE id = :id"
    ), {"id": cid})).mappings().first()
    if not conv:
        return {}
    msgs = (await db.execute(sql_text("""
    SELECT id, role, content, sources, latency_ms, model, cache_hit, created_at
    FROM messages WHERE conversation_id = :id ORDER BY created_at
    """), {"id": cid})).mappings().all()
    return {
        "conversation": {
            "id": str(conv["id"]),
            "session_id": conv["session_id"],
            "user_ip": str(conv["user_ip"]) if conv["user_ip"] else None,
            "user_agent": conv["user_agent"],
            "created_at": conv["created_at"].isoformat(),
        },
        "messages": [
            {
                "id": str(m["id"]),
                "role": m["role"],
                "content": m["content"],
                "sources": m["sources"],
                "latency_ms": m["latency_ms"],
                "model": m["model"],
                "cache_hit": m["cache_hit"],
                "created_at": m["created_at"].isoformat(),
            } for m in msgs
        ],
    }