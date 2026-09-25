"""
Loads BGE-M3 embedder and BGE reranker ONCE per process.
Optimized for CPU inference with thread pooling.
"""
import torch
import logging
import os
from sentence_transformers import SentenceTransformer, CrossEncoder
from config import settings

logger = logging.getLogger(__name__)


def _resolve_cache_folder() -> str | None:
    """Resolve HF model cache dir.

    - In Docker, HF_HOME=/app/models (exists, has models) -> use it.
    - On Windows local dev, .env may point HF_HOME to an empty dir while
      the real cache lives in ~/.cache/huggingface -> return None so
      huggingface_hub uses its default cache instead of re-downloading.
    """
    for env_key in ("HF_HOME", "TRANSFORMERS_CACHE", "HF_HUB_CACHE", "SENTENCE_TRANSFORMERS_HOME"):
        cand = os.environ.get(env_key)
        if not cand:
            continue
        cand = os.path.expandvars(os.path.expanduser(cand))
        hub = os.path.join(cand, "hub")
        # Use it only if it looks populated; otherwise fall through to default cache
        if os.path.isdir(hub) and os.listdir(hub):
            return cand
        if os.path.isdir(cand) and os.listdir(cand):
            return cand
    # Common container path — use only if populated
    if os.path.isdir("/app/models") and os.listdir("/app/models"):
        return "/app/models"
    return None  # -> HF default cache (~/.cache/huggingface)

# CPU threads — optimized for concurrent requests
torch.set_num_threads(4)
# Disable grad for inference optimization
torch.set_grad_enabled(False)

_embedder: SentenceTransformer | None = None
_reranker: CrossEncoder | None = None


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        logger.info(f"Loading embedder: {settings.EMBEDDING_MODEL}")
        _embedder = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            cache_folder=_resolve_cache_folder(),
            device="cpu",
            trust_remote_code=True,
        )
        _embedder.max_seq_length = settings.EMBEDDING_MAX_LEN
        _embedder.eval()
        logger.info("Embedder loaded ✅")
    return _embedder


def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        logger.info(f"Loading reranker: {settings.RERANK_MODEL}")
        _reranker = CrossEncoder(
            settings.RERANK_MODEL,
            cache_folder=_resolve_cache_folder(),
            device="cpu",
            max_length=settings.RERANK_MAX_LEN,
        )
        _reranker.model.eval()
        logger.info("Reranker loaded ✅")
    return _reranker