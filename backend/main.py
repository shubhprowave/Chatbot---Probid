
"""
FastAPI application entry point.

Wires together:
- CORS
- API routers under /api/* (chat, ingest, feedback, admin, metrics, eval, user)
- React frontend (chatbot at /, admin SPA at /admin/*) served from frontend/dist
- ML model warmup on startup
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging
import os

from config import settings
from models import get_embedder, get_reranker
from api import chat, ingest, feedback, admin, metrics
from api import eval as eval_api
from api import users


# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("rag-api")


# -------------------------------------------------------------------
# Lifespan — warm ML models so first request isn't slow
# -------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 60)
    log.info("Starting RAG API")
    log.info("=" * 60)

    log.info("Warming embedder: %s", settings.EMBEDDING_MODEL)
    get_embedder()
    log.info("Embedder loaded ✅")

    log.info("Warming reranker: %s", settings.RERANK_MODEL)
    get_reranker()
    log.info("Reranker loaded ✅")

    log.info("Config:")
    log.info("  LLM_MODEL       = %s", settings.LLM_MODEL)
    log.info("  LLM_MODEL_FAST  = %s", settings.LLM_MODEL_FAST)
    log.info("  LLM_URL        = %s", settings.LLM_BASE_URL)
    log.info("  LLM_KEY        = %s", "set" if settings.LLM_API_KEY else "MISSING")
    log.info("  DATABASE_URL    = %s", settings.DATABASE_URL.split("@")[-1])
    log.info("  REDIS_URL       = %s", settings.REDIS_URL)
    log.info("  CORS_ORIGINS    = %s", settings.cors_list)

    log.info("Models ready ✅ — API is live")
    yield

    log.info("Shutting down RAG API")


# -------------------------------------------------------------------
# App
# -------------------------------------------------------------------
app = FastAPI(
    title="Company RAG Bot",
    description="Production RAG chatbot API with Postgres + pgvector, self-hosted LLMs",
    version="1.0.0",
    lifespan=lifespan,
)


# -------------------------------------------------------------------
# CORS
# -------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE", "PUT", "PATCH"],
    allow_headers=["*"],
    allow_credentials=False,
    expose_headers=["*"],
)


# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))          # backend/
_PROJECT_ROOT = os.path.dirname(_HERE)                        # AI_Chatbot - V1/


# -------------------------------------------------------------------
# Routers
# -------------------------------------------------------------------
# All JSON APIs live under /api/* so that:
#   /           -> React chatbot (public)
#   /admin/*    -> React admin SPA (UI; API itself still enforces ADMIN_TOKEN)
#   /api/*      -> backend endpoints (also reachable by other sites as "the API")
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(ingest.router, prefix="/api", tags=["ingest"])
app.include_router(feedback.router, prefix="/api", tags=["feedback"])
app.include_router(admin.router, prefix="/api", tags=["admin"])
app.include_router(metrics.router, prefix="/api", tags=["metrics"])
app.include_router(eval_api.router, prefix="/api", tags=["eval"])
app.include_router(users.router, prefix="/api", tags=["user"])


# -------------------------------------------------------------------
# Health check
# -------------------------------------------------------------------
@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "rag-api", "version": "1.0.0"}


# -------------------------------------------------------------------
# Frontend (React build) — served directly, no reverse proxy needed:
#   /           -> public chatbot (embeddable in other sites)
#   /admin/*    -> admin SPA (UI token-gated; API still enforces ADMIN_TOKEN)
# Registered AFTER the API routers so /api/* always matches first.
# -------------------------------------------------------------------
_CANDIDATE_DIST_DIRS = [
    os.path.join(_PROJECT_ROOT, "frontend", "dist"),          # flat layout
    os.path.join(_PROJECT_ROOT, "frontend", "dashboard", "dist"),  # legacy layout
    os.path.join(_PROJECT_ROOT, "dashboard", "dist"),
]
DIST_DIR = next(
    (d for d in _CANDIDATE_DIST_DIRS if os.path.isdir(d)),
    _CANDIDATE_DIST_DIRS[0],
)
DIST_INDEX = os.path.join(DIST_DIR, "index.html")

if os.path.isfile(DIST_INDEX):
    _ASSETS_DIR = os.path.join(DIST_DIR, "assets")
    if os.path.isdir(_ASSETS_DIR):
        app.mount("/assets", StaticFiles(directory=_ASSETS_DIR), name="assets")
        log.info("Frontend assets mounted from %s", _ASSETS_DIR)

    @app.get("/", tags=["system"], include_in_schema=False)
    async def spa_root():
        return FileResponse(DIST_INDEX)

    @app.get("/admin", tags=["system"], include_in_schema=False)
    async def spa_admin():
        return FileResponse(DIST_INDEX)

    @app.get("/admin/{full_path:path}", tags=["system"], include_in_schema=False)
    async def spa_admin_fallback(full_path: str):
        return FileResponse(DIST_INDEX)

    log.info("Frontend SPA served from %s (chatbot at /, admin at /admin)", DIST_DIR)
else:

    @app.get("/", tags=["system"])
    async def root():
        return {
            "service": "Company RAG Bot",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
            "chatbot": "/",
            "admin": "/admin",
            "note": "frontend not built — run `npm run build` in frontend/",
        }