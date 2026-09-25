import httpx
from config import settings
from rag.llm_client import chat_completion


ROUTER_PROMPT = """Classify the user question as SIMPLE or COMPLEX.
SIMPLE = greeting, thanks, chit-chat, casual.
COMPLEX = needs information lookup, explanation, multi-part.
Reply with ONE word only: SIMPLE or COMPLEX.

Question: {q}
Answer:"""


async def route(question: str) -> str:
    try:
        ans = await chat_completion(
            [{"role": "user", "content": ROUTER_PROMPT.format(q=question)}],
            model=settings.LLM_MODEL_FAST,
            temperature=0.0,
            max_tokens=4,
        )
        return "SIMPLE" if "SIMPLE" in ans.upper() else "COMPLEX"
    except Exception:
        # Fallback: default to COMPLEX (safer, does retrieval)
        return "COMPLEX"