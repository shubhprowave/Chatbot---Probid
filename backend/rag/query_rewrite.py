import re
from config import settings
from rag.llm_client import chat_completion


# Hinglish (Roman-script Hindi) -> English, applied BEFORE embedding/BM25
# so English documents match Hinglish queries. Ordered longest-first.
HINGLISH_TO_ENGLISH = [
    ("ke baare me", "about"),
    ("ke bare me", "about"),
    ("ke baare mein", "about"),
    ("ke baare", "about"),
    ("ke bare", "about"),
    ("jaan na", "know"),
    ("jan na", "know"),
    ("janna", "know"),
    ("jaankari", "information"),
    ("jankari", "information"),
    ("bataiye", "tell"),
    ("batao", "tell"),
    ("chahiye", "need"),
    ("mujhe", "me"),
    ("tumhe", "you"),
    ("tujhe", "you"),
    ("mujhko", "me"),
    ("kyaa", "what"),
    ("kya", "what"),
    ("kaise", "how"),
    ("kahan", "where"),
    ("kaun", "who"),
    ("kab", "when"),
    ("kitne", "how many"),
    ("kitna", "how much"),
    ("kya hai", "what is"),
    ("hai", "is"),
    ("hain", "are"),
    ("nahi", "not"),
    ("karna", "do"),
    ("karne", "do"),
    ("karo", "do"),
    ("sakta", "can"),
    ("sakte", "can"),
    ("chahiye", "need"),
    ("lagta", "required"),
    ("lagna", "required"),
    ("lagti", "required"),
]

_normalize_parts = [
    (re.compile(rf"\b{re.escape(h)}\b", re.IGNORECASE), e)
    for h, e in HINGLISH_TO_ENGLISH
]


def normalize_query(query: str) -> str:
    """Turn obvious Hinglish words into English so retrieval matches better.

    English queries are left essentially unchanged.
    """
    text = " " + query.strip() + " "
    for pattern, repl in _normalize_parts:
        text = pattern.sub(repl, text)
    return text.strip()


REWRITE_PROMPT = """Rewrite the user's question into 3 different search queries
that would help find relevant documents. Use synonyms and related terms.
Return ONLY the queries, one per line, no numbering, no bullets.

Question: {q}
"""


async def rewrite_query(question: str, history: list) -> list[str]:
    try:
        text = await chat_completion(
            [{"role": "user", "content": REWRITE_PROMPT.format(q=question)}],
            model=settings.LLM_MODEL_FAST,
            temperature=0.2,
            max_tokens=120,
        )
        queries = [
            line.strip(" -•1234567890.").strip()
            for line in text.split("\n")
            if line.strip() and len(line.strip()) > 5
        ]
        # Always include original question first
        out = [question]
        for q in queries[:3]:
            if q and q != question:
                out.append(q)
        return out
    except Exception:
        return [question]