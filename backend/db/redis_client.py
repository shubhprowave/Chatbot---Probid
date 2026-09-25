import redis.asyncio as redis
import json, hashlib
from config import settings

r = redis.from_url(settings.REDIS_URL, decode_responses=True)

def make_cache_key(question: str, tenant_id: str) -> str:
    h = hashlib.sha256(question.lower().strip().encode()).hexdigest()[:32]
    return f"rag:qa:{tenant_id}:{h}"

async def cache_get(key: str):
    try:
        v = await r.get(key)
        return json.loads(v) if v else None
    except Exception:
        return None

async def cache_set(key: str, value: dict, ttl: int = None):
    try:
        await r.set(key, json.dumps(value), ex=ttl or settings.CACHE_TTL)
    except Exception:
        pass