"""
Dynamic chunking engine.

Documents can have any structure, so we expose a registry of chunking
strategies. Each strategy knows how to split text AND which parameters it
accepts, so the dashboard can render a dynamic form straight from this
registry. New strategies can be added here without touching the API or UI.

Endpoint contract: ``GET /admin/chunking/strategies`` returns this registry
(minus the internal functions) for the dashboard.
"""
import json
import re

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    RecursiveJsonSplitter,
)


# ---------------------------------------------------------------
# Parameter schemas — these drive the dynamic UI form.
# ---------------------------------------------------------------
def _int_param(label, default, min_, max_, step=1):
    return {
        "type": "int",
        "label": label,
        "default": default,
        "min": min_,
        "max": max_,
        "step": step,
    }


# ---------------------------------------------------------------
# Splitter implementation helpers
# ---------------------------------------------------------------
def _clean(text: str) -> str:
    return (text or "").strip()


def _split_recursive(text: str, params: dict) -> list[str]:
    size = int(params.get("chunk_size", 800))
    overlap = int(params.get("chunk_overlap", 120))
    separators = ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", ". ", "! ", "? ", " "]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=separators,
        length_function=len,
    )
    return splitter.split_text(text)


def _split_fixed(text: str, params: dict) -> list[str]:
    """Deterministic fixed-size chunks (no separator awareness)."""
    size = int(params.get("chunk_size", 800))
    overlap = int(params.get("chunk_overlap", 0))
    if size <= 0:
        size = 800
    if overlap >= size:
        overlap = 0
    step = max(size - overlap, 1)
    return [text[i:i + size] for i in range(0, len(text), step)]


def _split_long_text(text: str, max_chars: int, overlap: int) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chars,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", "! ", "? ", " "],
        length_function=len,
    )
    pieces = splitter.split_text(text)
    # Guard: if separators never matched, pieces can stay oversized.
    # Fall back to fixed-size so nothing exceeds max_chars.
    if all(len(p) <= max_chars for p in pieces):
        return pieces
    return _split_fixed(text, {"chunk_size": max_chars, "chunk_overlap": overlap if overlap < max_chars else 0})


_MD_HEADERS = [
    ("#", "H1"),
    ("##", "H2"),
    ("###", "H3"),
    ("####", "H4"),
    ("#####", "H5"),
    ("######", "H6"),
]


def _split_markdown(text: str, params: dict) -> list[str]:
    """Keep heading hierarchy so sections stay context-aware."""
    max_chars = int(params.get("max_chars", 1200))
    overlap = int(params.get("chunk_overlap", 100))

    try:
        section_splitter = MarkdownHeaderTextSplitter(_MD_HEADERS, strip_headers=False)
        sections = section_splitter.split_text(text)
    except Exception:
        sections = []

    if not sections:
        # No markdown headings found — fall back to plain recursive split.
        return _split_recursive(text, {"chunk_size": max_chars, "chunk_overlap": overlap})

    out = []
    for sec in sections:
        content = sec.page_content or ""
        headers = sec.metadata or {}
        prefix = " | ".join(f"{name}: {val}" for name, val in headers.items() if val)
        for piece in _split_long_text(content, max_chars, overlap):
            piece = _clean(piece)
            if not piece:
                continue
            if prefix:
                piece = f"{prefix}\n\n{piece}"
            out.append(piece)
    return out


def _split_json(text: str, params: dict) -> list[str]:
    max_chars = int(params.get("max_chars", 1200))
    min_chars = int(params.get("min_chars", 0))

    try:
        data = json.loads(text)
    except Exception:
        data = None

    # Not valid JSON (or a scalar) — just treat as plain text.
    if data is None or isinstance(data, (str, int, float, bool)):
        return _split_recursive(text, {"chunk_size": max_chars, "chunk_overlap": 0})

    splitter = RecursiveJsonSplitter(
        max_chunk_size=max_chars,
        min_chunk_size=min_chars if min_chars > 0 else None,
    )
    try:
        # Handles lists, dicts, nested structures.
        return [c for c in splitter.split_text(data) if c]
    except Exception:
        return []


_PAGE_BREAK = "\f"


def _split_pages(text: str, params: dict) -> list[str]:
    """One chunk per page. Page boundaries are marked with a form feed by the
    PDF loader. If no page markers exist, falls back to paragraph chunks."""
    min_chars = int(params.get("min_chars", 30))
    if _PAGE_BREAK in text:
        pages = [p.strip() for p in text.split(_PAGE_BREAK)]
        pages = [p for p in pages if p and len(p) >= min_chars]
        return pages or _split_paragraphs(text, params)
    return _split_paragraphs(text, params)


def _split_paragraphs(text: str, params: dict) -> list[str]:
    """One chunk per paragraph (blank-line delimited). Paragraphs longer than
    max_chars are further split structurally."""
    max_chars = int(params.get("max_chars", 1600))
    overlap = int(params.get("chunk_overlap", 0))

    paras = [p.strip() for p in re.split(r"\n\s*\n", text)]
    paras = [p for p in paras if p]

    if not paras:
        return _split_recursive(text, {"chunk_size": max_chars, "chunk_overlap": overlap})

    out: list[str] = []
    for p in paras:
        if len(p) > max_chars:
            out.extend(_split_long_text(p, max_chars, overlap))
        else:
            out.append(p)
    return out


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+", re.MULTILINE)


def _split_sentences(text: str, params: dict) -> list[str]:
    """Group sentences into chunks of N sentences each (with overlap).
    Very long sentences are further split by character budget."""
    per_chunk = int(params.get("sentences_per_chunk", 5))
    overlap = int(params.get("sentence_overlap", 1))
    max_chars = int(params.get("max_chars", 1200))

    sentences = [s.strip() for s in _SENTENCE_RE.split(text)]
    sentences = [s for s in sentences if s]

    if not sentences:
        return _split_recursive(text, {"chunk_size": max_chars, "chunk_overlap": overlap or 0})

    if per_chunk < 1:
        per_chunk = 1
    if overlap >= per_chunk:
        overlap = 0
    step = max(per_chunk - overlap, 1)

    chunks: list[str] = []
    for i in range(0, len(sentences), step):
        group = sentences[i:i + per_chunk]
        joined = " ".join(group)
        if len(joined) > max_chars:
            chunks.extend(_split_long_text(joined, max_chars, overlap and 50 or 0))
        else:
            chunks.append(joined)
    return chunks


# ---------------------------------------------------------------
# Registry
# ---------------------------------------------------------------
CHUNK_STRATEGIES: dict[str, dict] = {
    "auto": {
        "label": "Auto-detect",
        "description": (
            "Pick the best strategy automatically from the file type "
            "(RECOMMENDED for unknown document structures)."
        ),
        "auto": True,
        "params": {},
    },
    "recursive": {
        "label": "Recursive character",
        "description": (
            "Splits on paragraph, sentence and word boundaries. Good default "
            "for prose (PDFs, Word, plain text)."
        ),
        "split": _split_recursive,
        "params": {
            "chunk_size": _int_param("Chunk size (chars)", 800, 100, 4000),
            "chunk_overlap": _int_param("Overlap (chars)", 120, 0, 400),
            "min_chars": _int_param("Min chunk length", 30, 0, 500),
        },
    },
    "fixed": {
        "label": "Fixed size",
        "description": (
            "Hard character-limit chunks, no separator awareness. Use for "
            "arbitrary/unstructured text where boundaries don't matter."
        ),
        "split": _split_fixed,
        "params": {
            "chunk_size": _int_param("Chunk size (chars)", 800, 100, 4000),
            "chunk_overlap": _int_param("Overlap (chars)", 0, 0, 400),
            "min_chars": _int_param("Min chunk length", 30, 0, 500),
        },
    },
    "markdown": {
        "label": "Markdown structure",
        "description": (
            "Keeps headings as context — ideal for .md docs with sections "
            "# / ## / ### so retrieval is aware of the structure."
        ),
        "split": _split_markdown,
        "params": {
            "max_chars": _int_param("Max section chars", 1200, 200, 4000),
            "chunk_overlap": _int_param("Overlap (chars)", 100, 0, 400),
            "min_chars": _int_param("Min chunk length", 30, 0, 500),
        },
    },
    "json": {
        "label": "JSON structure",
        "description": (
            "Splits JSON documents by nested keys/arrays so each chunk keeps "
            "its key path. Good for configs, specs, structured data."
        ),
        "split": _split_json,
        "params": {
            "max_chars": _int_param("Max chunk chars", 1200, 200, 4000),
            "min_chars": _int_param("Min chunk length", 0, 0, 1000),
        },
    },
    "page": {
        "label": "Page",
        "description": (
            "One chunk per page. Uses real page boundaries from PDFs "
            "(falls back to paragraphs if the format has no page info)."
        ),
        "split": _split_pages,
        "params": {
            "min_chars": _int_param("Min chunk length", 30, 0, 500),
        },
    },
    "paragraph": {
        "label": "Paragraph",
        "description": (
            "One chunk per paragraph (blank-line delimited). Long paragraphs "
            "are split into multiple chunks at sentence/word boundaries."
        ),
        "split": _split_paragraphs,
        "params": {
            "max_chars": _int_param("Max paragraph chars", 1600, 200, 4000),
            "chunk_overlap": _int_param("Overlap (chars)", 0, 0, 400),
            "min_chars": _int_param("Min chunk length", 30, 0, 500),
        },
    },
    "sentence": {
        "label": "Sentence",
        "description": (
            "Groups consecutive sentences into chunks (with configurable "
            "sentences per chunk + overlap). Good for Q&A style content."
        ),
        "split": _split_sentences,
        "params": {
            "sentences_per_chunk": _int_param("Sentences per chunk", 5, 1, 50),
            "sentence_overlap": _int_param("Overlap (sentences)", 1, 0, 20),
            "max_chars": _int_param("Max chunk chars", 1200, 200, 4000),
            "min_chars": _int_param("Min chunk length", 30, 0, 500),
        },
    },
}

# File extension -> default strategy when "auto" is requested.
_AUTO_MAP = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".json": "json",
    ".pdf": "page",
}


def resolve_strategy(strategy: str, filename: str | None = None) -> str:
    """Resolve 'auto' to a concrete strategy, or validate a concrete one."""
    name = (strategy or "auto").strip().lower()
    if name == "auto":
        if filename:
            ext = filename.lower()
            # keep longest suffix match
            best = None
            for suffix, strat in _AUTO_MAP.items():
                if ext.endswith(suffix):
                    best = strat
            if best:
                return best
        return "recursive"
    if name not in CHUNK_STRATEGIES or "split" not in CHUNK_STRATEGIES[name]:
        raise ValueError(f"Unknown chunking strategy: {name}")
    return name


def list_strategies() -> list[dict]:
    """Public metadata (no functions) for the dashboard form."""
    out = []
    for name, cfg in CHUNK_STRATEGIES.items():
        out.append({
            "id": name,
            "label": cfg["label"],
            "description": cfg["description"],
            "auto": cfg.get("auto", False),
            "params": cfg.get("params", {}),
        })
    return out


def _merge_params(cfg: dict, raw: dict | None, limit_keys: bool = True) -> dict:
    params = cfg.get("params", {})
    merged = {}
    for key, schema in params.items():
        merged[key] = schema["default"]
    for key, val in (raw or {}).items():
        schema = params.get(key)
        if not schema:
            if limit_keys:
                continue  # ignore unknown params
            merged[key] = val
            continue
        try:
            num = int(val)
            if "min" in schema and num < schema["min"]:
                num = schema["min"]
            if "max" in schema and num > schema["max"]:
                num = schema["max"]
            merged[key] = num
        except (TypeError, ValueError):
            pass  # keep default
    return merged


def chunk_document(
    text: str,
    strategy: str = "auto",
    params: dict | None = None,
    metadata: dict | None = None,
    filename: str | None = None,
) -> dict:
    """Chunk a document with the chosen strategy.

    Returns {
        "chunks": [{"text", "chunk_index", "char_count", ...metadata}],
        "strategy": <resolved strategy id>,
        "params": <effective params>,
    }
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return {"chunks": [], "strategy": resolve_strategy(strategy, filename), "params": (params or {})}

    resolved = resolve_strategy(strategy, filename)
    cfg = CHUNK_STRATEGIES[resolved]
    merged = _merge_params(cfg, params)
    min_chars = int(merged.get("min_chars", 30))

    pieces = cfg["split"](cleaned, merged) or []
    meta = dict(metadata or {})
    chunks = []
    idx = 0
    for p in pieces:
        p = _clean(p)
        if not p:
            continue
        if len(p) < min_chars:
            continue
        chunks.append({
            "text": p,
            "chunk_index": idx,
            "char_count": len(p),
            **meta,
        })
        idx += 1

    return {"chunks": chunks, "strategy": resolved, "params": merged}


def semantic_chunk(text: str, metadata: dict) -> list[dict]:
    """Backward-compatible wrapper for the old behaviour."""
    return chunk_document(text, "recursive", None, metadata)["chunks"]