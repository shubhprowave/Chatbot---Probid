"""Natural-language → SQL over the tender database, using the Groq LLM."""
import logging
import re
from typing import Any

from config import settings
from rag.llm_client import chat_completion
from rag.generator import detect_language
from tenders import mysql as tdb

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Reject raw SQL / injection-style input
# ---------------------------------------------------------------------
_SQL_KEYWORDS = (
    "select", "insert", "update", "delete", "drop", "alter", "truncate",
    "create", "replace", "grant", "revoke", "union", "exec", "execute",
    "declare", "show", "describe",
)

_SQL_START_RE = re.compile(
    r"^\s*(select|insert|update|delete|drop|alter|truncate|create|replace|"
    r"grant|revoke|union|exec|execute|declare)\b",
    re.IGNORECASE,
)

_SQL_SHOW_RE = re.compile(
    r"^\s*(show\s+(tables|databases|columns|fields|full|create|grants|index|status|variables|processlist)"
    r"|use\s+`?\w+`?\s*;"
    r"|describe\s+`?\w+`?\s*;"
    r"|desc\s+`?\w+`?\s*;)\s*$",
    re.IGNORECASE,
)

_SQL_SELECT_FROM_RE = re.compile(r"\bselect\b[\s\S]{0,80}?\bfrom\b", re.IGNORECASE)
_SQL_DML_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|replace|union)\b",
    re.IGNORECASE,
)
_SQL_TARGET_RE = re.compile(
    r"\b(into|from|table|database|set|where|select|values|join)\b",
    re.IGNORECASE,
)
_SQL_TAUTOLOGY_RE = re.compile(r"\bor\b\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?", re.IGNORECASE)


def looks_like_sql(text: str) -> bool:
    """Heuristic: does the message look like a raw SQL statement instead of a question?"""
    t = (text or "").strip()
    if not t:
        return False
    low = t.lower()

    if "--" in t or "/*" in t or "*/" in t:
        return True
    if _SQL_START_RE.match(low):
        return True
    if _SQL_SHOW_RE.match(low):
        return True
    if _SQL_SELECT_FROM_RE.search(low):
        return True
    if _SQL_DML_RE.search(low) and _SQL_TARGET_RE.search(low):
        return True
    if _SQL_TAUTOLOGY_RE.search(low):
        return True
    if t.endswith(";") and any(k in low for k in _SQL_KEYWORDS):
        return True
    return False


SQL_REJECTION = {
    "english": "I don't have information about that.",
    "hinglish": "Mujhe is baare mein jaankari nahi hai.",
    "hindi": "मुझे इस बारे में जानकारी नहीं है।",
}


def build_sql_rejection(question: str) -> str:
    lang = detect_language(question) if question else "english"
    return SQL_REJECTION.get(lang, SQL_REJECTION["english"])


# ---------------------------------------------------------------------
# Routing: is the user asking to search the tender database?
# ---------------------------------------------------------------------
ROUTER_PROMPT = """You route messages for a chatbot about Indian government tenders.
Classify the user's message into exactly one category:

- TENDER: the user wants to SEARCH, FIND or LIST actual tenders/bids from a tender database
  (by product/category e.g. CCTV, by state/city, by agency/department, by amount, by date, "live" or "fresh" tenders).
- DOC: everything else - questions about services, GeM/OEM registration, required documents,
  process, fees, company information, greetings, or general conversation.

Reply with ONE word only: TENDER or DOC.

Message: {q}
Answer:"""


async def is_tender_query(question: str) -> bool:
    if not settings.TENDER_ENABLED:
        return False
    try:
        ans = await chat_completion(
            [{"role": "user", "content": ROUTER_PROMPT.format(q=question)}],
            model=settings.LLM_MODEL_FAST,
            temperature=0.0,
            max_tokens=4,
        )
        return "TENDER" in ans.upper()
    except Exception as e:
        log.warning("[tender] router failed: %s", e)
        return False


# ---------------------------------------------------------------------
# SQL generation
# ---------------------------------------------------------------------
SCHEMA = """Table: all_tenders  (read-only view combining live and fresh tenders)

Columns (MySQL):
  source              VARCHAR   -- 'live' or 'fresh'
  ourrefno            INT       -- the tender's PBID (unique reference). Displayed as PBID.
  TenderNo            VARCHAR   -- portal tender number
  purfromdate         DATE
  submitdate          DATE      -- bid DUE DATE (bid submission deadline)
  opendate            DATE      -- tender OPENING date
  bid_submission_time TIME
  tender_opening_time TIME
  ContractType        VARCHAR
  BidValidity         VARCHAR
  tenderamount        VARCHAR   -- tender value (numeric string, e.g. '1000000.00')
  earnestamount       VARCHAR   -- EMD
  doccost             VARCHAR
  org_name            VARCHAR   -- agency / department
  address             TEXT
  Work                LONGTEXT  -- tender description / work (case-insensitive LIKE works)
  state_name          VARCHAR
  city                VARCHAR
  dt                  DATE
  tendertype          VARCHAR
  form_of_contract    VARCHAR
  pincode             INT
  sector              INT
  link                TEXT"""

SQL_SYSTEM_PROMPT = f"""You are a MySQL expert. Convert the user's natural-language request about
Indian government tenders into ONE read-only SELECT statement.

{SCHEMA}

Rules:
- Query ONLY the all_tenders table. Never use any other table.
- Output ONLY the SQL statement. No markdown fences, no explanation, no trailing text.
- Only SELECT. Never INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE.
- Text matching is already case-insensitive; use LIKE '%keyword%'.
- Match city and state loosely, e.g. (city LIKE '%ahmedabad%' OR state_name LIKE '%gujarat%').
- For category/product keywords search the Work description, e.g. Work LIKE '%cctv%'.
- Match ONLY the keyword(s) the user actually said. Do NOT add synonyms, related words or broader terms (e.g. "constructions" -> ONLY Work LIKE '%construction%'; do not also match building/road/infrastructure/civil unless the user said them).
- When the user asks HOW MANY (kitne/kaise/count), return SELECT COUNT(*) with the filters.
- When listing tenders, ALWAYS select all standard columns: ourrefno, TenderNo, Work, org_name, state_name, city, tenderamount, submitdate, opendate, source, link. Do NOT return partial rows.
- Always ORDER BY submitdate DESC and add LIMIT 10 unless the user asks for a different number (max 50).
- Prefer the most relevant results; do not return rows unrelated to the request."""


def _clean_sql(raw: str) -> str:
    sql = (raw or "").strip()
    sql = re.sub(r"^```[a-zA-Z]*\s*", "", sql)
    sql = re.sub(r"```\s*$", "", sql).strip()
    return sql.rstrip(";").strip()


_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|replace|grant|revoke|call|"
    r"merge|handler|rename|lock|unlock|prepare|execute|load_file|outfile|dumpfile|"
    r"information_schema|performance_schema|sys\.|mysql\.|sleep|benchmark)\b",
    re.IGNORECASE,
)


def validate_sql(raw: str, limit: int) -> str:
    """Return a safe, single-statement SELECT against all_tenders, or raise ValueError."""
    sql = _clean_sql(raw)
    if not sql:
        raise ValueError("empty SQL")
    if ";" in sql:
        raise ValueError("multiple statements are not allowed")
    if not re.match(r"^\s*(select|with)\b", sql, re.IGNORECASE):
        raise ValueError("only SELECT queries are allowed")
    if _FORBIDDEN.search(sql):
        raise ValueError("query contains a forbidden keyword")

    tables = re.findall(r"\b(?:from|join)\s+`?([A-Za-z_][\w.]*)`?", sql, re.IGNORECASE)
    if not tables:
        raise ValueError("no table found in query")
    for t in tables:
        if t.lower() != tdb.VIEW_NAME:
            raise ValueError(f"table not allowed: {t}")

    m = re.search(r"\blimit\s+(\d+)", sql, re.IGNORECASE)
    if m:
        if int(m.group(1)) > 50:
            sql = re.sub(r"\blimit\s+\d+", "LIMIT 50", sql, flags=re.IGNORECASE)
    else:
        sql = f"{sql} LIMIT {limit}"
    return sql


async def generate_sql(question: str, history: list) -> str:
    messages: list[dict] = [{"role": "system", "content": SQL_SYSTEM_PROMPT}]
    for m in history[-4:]:
        if m.get("role") in ("user", "assistant"):
            messages.append({"role": m["role"], "content": str(m["content"])[:500]})
    messages.append({"role": "user", "content": question})

    limit = settings.TENDER_RESULT_LIMIT
    last_err = ""
    for attempt in range(2):
        raw = await chat_completion(
            messages,
            model=settings.LLM_MODEL_FAST,
            temperature=0.0,
            max_tokens=400,
        )
        try:
            return validate_sql(raw, limit)
        except ValueError as e:
            last_err = str(e)
            log.warning("[tender] invalid SQL (attempt %d): %s | raw=%r", attempt + 1, e, raw[:300])
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"That query was rejected ({e}). Output ONLY a corrected single SELECT against all_tenders.",
            })
    raise ValueError(f"could not generate valid SQL: {last_err}")


# ---------------------------------------------------------------------
# Language-aware intro
# ---------------------------------------------------------------------
INTROS = {
    "hinglish": {
        "found": "Yeh rahe aapke search se mile {n} tender (live + fresh dono se):",
        "none": "Maaf kijiye, aapki search se milta-julta koi tender nahi mila. Category, sheher ya state thoda alag tarike se batayein.",
    },
    "hindi": {
        "found": "आपकी खोज से मिले {n} टेंडर (लाइव और फ्रेश दोनों में से):",
        "none": "क्षमा करें, आपकी खोज से मेल खाता कोई टेंडर नहीं मिला। कृपया श्रेणी, शहर या राज्य बताएं।",
    },
    "english": {
        "found": "Here are {n} tender(s) matching your search (from live and fresh):",
        "none": "I couldn't find any tenders matching your search. Try a different category, city or state.",
    },
}


def build_intro(question: str, count: int) -> str:
    lang = detect_language(question) if question else "english"
    texts = INTROS.get(lang, INTROS["english"])
    return texts["found"].format(n=count) if count else texts["none"]


COUNT_MSGS = {
    "english": "There {are} {n} tender(s) matching your search right now (from live + fresh).",
    "hinglish": "Abhi aapki search se {n} tender milte hain (live + fresh dono se).",
    "hindi": "अभी आपकी खोज से {n} टेंडर मिलते हैं (लाइव और फ्रेश दोनों से)।",
}


def build_count_message(question: str, count: int) -> str:
    lang = detect_language(question) if question else "english"
    text = COUNT_MSGS.get(lang, COUNT_MSGS["english"]).format(n=count)
    if lang == "english":
        text = text.format(are="is" if count == 1 else "are")
    return text


EMAIL_FOOTERS = {
    "english": "\n\nFor further assistance, you can email us at sales@probidconsultants.com or call us at +91 70166 28865.",
    "hinglish": "\n\nAur madad ke liye, aap sales@probidconsultants.com par email kar sakte hain ya +91 70166 28865 par call kar sakte hain.",
    "hindi": "\n\nआगे की सहायता के लिए, आप sales@probidconsultants.com पर ईमेल कर सकते हैं या +91 70166 28865 पर कॉल कर सकते हैं।",
}


def _email_footer(question: str) -> str:
    lang = detect_language(question) if question else "english"
    return EMAIL_FOOTERS.get(lang, EMAIL_FOOTERS["english"])


_COUNT_SQL_RE = re.compile(
    r"\bcount\s*\(|\bsum\s*\(|\bavg\s*\(|\bmin\s*\(|\bmax\s*\(\b",
    re.IGNORECASE,
)


def is_count_query(sql: str) -> bool:
    """True if the generated SQL is an aggregate (COUNT/SUM/...) returning a number."""
    return bool(_COUNT_SQL_RE.search(sql or ""))


async def _stream_text(text: str):
    for token in text.split(" "):
        yield token + " "


def _dedupe(rows: list[dict], limit: int) -> list[dict]:
    """A tender can exist in both live and fresh; keep one row per PBID (prefer live)."""
    seen: dict[Any, dict] = {}
    order: list[Any] = []
    for r in rows:
        key = r.get("ourrefno")
        if key in seen:
            if seen[key].get("source") != "live" and r.get("source") == "live":
                seen[key] = r
            continue
        seen[key] = r
        order.append(key)
    return [seen[k] for k in order][:limit]


async def answer_tender_query(question: str, history: list) -> dict[str, Any]:
    """Generate SQL, run it, and return the intro + structured rows."""
    await tdb.ensure_view()
    sql = await generate_sql(question, history)

    # Aggregate / COUNT query (e.g. "kitne hain?") -> reply with the number, no table
    if is_count_query(sql):
        count = await tdb.run_count(sql)
        intro = build_count_message(question, count) + _email_footer(question)
        log.info("[tender] count q=%r -> %d", question, count)
        return {
            "answer_gen": _stream_text(intro),
            "sources": [],
            "tenders": [],
            "sql": sql,
            "model": settings.LLM_MODEL_FAST,
            "kind": "TENDER_COUNT",
            "cached": False,
        }

    limit = settings.TENDER_RESULT_LIMIT
    fetch_limit = min(limit * 3, 50)
    fetch_sql = re.sub(r"\blimit\s+\d+", f"LIMIT {fetch_limit}", sql, flags=re.IGNORECASE)
    rows = await tdb.run_query(fetch_sql, fetch_limit)
    rows = _dedupe(rows, limit)

    tenders = [tdb.format_row(r) for r in rows]
    intro = build_intro(question, len(tenders)) + _email_footer(question)
    log.info("[tender] q=%r -> %d rows", question, len(tenders))
    return {
        "answer_gen": _stream_text(intro),
        "sources": [],
        "tenders": tenders,
        "sql": sql,
        "model": settings.LLM_MODEL_FAST,
        "kind": "TENDER",
        "cached": False,
    }
