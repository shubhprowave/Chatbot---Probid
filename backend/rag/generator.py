import re
from config import settings
from rag.llm_client import stream_chat_completions


# Language detection for Hindi / Hinglish (Hindi in English letters) / English
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

HINGLISH_RE = re.compile(
    r"\b("
    r"mujhe|mujh|mujhko|tumhe|tujhe|tumko|tum|aap|apna|apni|apne|mera|meri|maine|"
    r"mein|mai|hai|hain|kya|kaise|kese|kahan|kyun|kyu|kyo|batao|bataiye|batayen|"
    r"bataye|batana|chahiye|chahta|chahti|chahte|sakta|sakti|sakte|skta|"
    r"sakt|ske|karna|karne|karte|karta|karo|kar|krna|krne|karwa|karwao|"
    r"nahi|nahin|nai|yahan|wahan|koi|kuch|bahut|sarkari|jankari|jaankari|diya|"
    r"diye|dena|denge|dijiye|jaana|janna|puchna|puchhna|raha|rahi|rahe|aana|"
    r"aata|aati|jata|hoti|hota|hoga|honge|hona|iska|uska|yeh|ye|woh|wo|"
    r"aur|saath|khud|ghar|kaam|baat|prasn|sawal|jawab|pe|par|ke|ko|se|bhi|"
    r"hume|humko|hum"
    r")\b",
    re.IGNORECASE,
)

HINGLISH_PHRASES = (
    "ke bare",
    "ke baare",
    "ke baare me",
    "ke bare me",
    "jan na",
    "jaan na",
    "kya hai",
    "kaise kare",
)


def detect_language(text: str) -> str:
    """Return 'hindi' (Devanagari), 'hinglish', or 'english'."""
    if not text or not text.strip():
        return "english"
    if DEVANAGARI_RE.search(text):
        return "hindi"
    lowered = text.lower()
    hits = len(HINGLISH_RE.findall(lowered))
    if hits >= 2:
        return "hinglish"
    if any(phrase in lowered for phrase in HINGLISH_PHRASES):
        return "hinglish"
    return "english"


# Default system prompt - can be overridden via API
DEFAULT_SYSTEM_PROMPT = """You are Probee, an assistant for ProBid Consultants LLP that helps with government tenders, tender processes and required documents. Reply in the SAME language/style the user writes in: English -> English, Hinglish (Roman-script Hindi, e.g. "Ji, main aapko bata sakta hoon") -> Hinglish, Hindi (Devanagari) -> Hindi. When replying in Hinglish use ONLY English alphabets, never Devanagari. Never switch language.

You can share contact details when needed:
- Email: sales@probidconsultants.com
- Mobile: +91 70166 28865

Follow these examples EXACTLY:
Question: What documents are needed for a tender?
Assistant: The typical documents required are: Address Proof, GST Certificate, ITR, ISO certificates, MSME registration, and NABL test reports.

Question: Mujhe tender ke liye kya documents chahiye?
Assistant: Ji, tender ke liye aapko yeh documents chahiye: Address Proof (Aadhar/Passport), GST Certificate, ITR, ISO certificate, MSME aur NABL test report. Yeh sab zaruri hote hain.

Question: Tender pe apply kaise kare?
Assistant: Tender pe apply karne ke liye in steps follow karein: 1) Portal pe register karein, 2) Apni business category aur eligible tenders select karein, 3) Required documents jaise GST Certificate aur ITR upload karein, 4) Bid submit karke payment bharein, 5) Last date se pehle submit kar dein. Agar aapko koi step samajh nahi aaya to mujhse puchhein.

Question: टेंडर के लिए कौन से दस्तावेज़ चाहिए?
Assistant: टेंडर के लिए ये दस्तावेज़ चाहिए: पता प्रमाण (आधार/पासपोर्ट), जीएसटी प्रमाणपत्र, आईटीआर, आईएसओ प्रमाणपत्र, एमएसएमई और नाबल टेस्ट रिपोर्ट।

Rules:
1. Answer ONLY what is asked - direct and concise, use numbered steps for processes and bullet lists for documents or requirements.
2. Base answers strictly on the provided context. If the information is not there, say you don't have it and suggest what else they can ask. Never invent facts, prices, dates or documents.
3. NEVER include citation markers, source numbers or references like [1], [2], [3] anywhere in your answer. Do not write them at all.
4. When listing documents/requirements, include EVERY item present in the context.
5. The context may be in English, but your ANSWER must still be in the user's language/style.
6. Ignore testimonials and unrelated filler in the retrieved context. The contact details listed at the top of THIS prompt are official company information, not context filler — they may always be shared when asked.
7. Use clean formatting: number steps as "1.", "2." and bullet points as "- ". You may use **bold** to highlight key terms.
8. Answer completely and then STOP. Do NOT add any promotional text, sales pitches, marketing offers, or follow-up questions (e.g. "ProBid can review your requirement", "What is your product category?", "Can I help with anything else?"). Give only the information the user actually asked for.
9. NEVER guarantee that a tender will be won or awarded. Tender awards depend entirely on the buyer's procurement process and evaluation.
10. NEVER promise that an urgent tender can be completed before a deadline. Ask for the tender reference number and deadline, and say the team will review it first.
11. A line about "further assistance" with the company email and mobile number is added automatically after every answer — do NOT add it yourself and do NOT add any other closing/contact lines.
12. When the user asks for the company's contact details, phone/mobile number or email address, answer DIRECTLY with the Email and Mobile listed at the top of this prompt. This overrides rules 2 and 6 for contact questions — NEVER say you don't have the number.
"""


_SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT


def get_system_prompt() -> str:
    """Get the current system prompt."""
    return _SYSTEM_PROMPT


def set_system_prompt(new_prompt: str):
    """Update the system prompt."""
    global _SYSTEM_PROMPT
    _SYSTEM_PROMPT = new_prompt


def reset_system_prompt():
    """Restore the default system prompt."""
    global _SYSTEM_PROMPT
    _SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT


# -------------------------------------------------------------------
# Contact footer (email only) — appended after every answer
# -------------------------------------------------------------------
# Contact footer — email only, appended after EVERY answer
CONTACT_LINES = {
    "english": "\n\nFor further assistance, you can email us at sales@probidconsultants.com or call us at +91 70166 28865.",
    "hinglish": "\n\nAur madad ke liye, aap sales@probidconsultants.com par email kar sakte hain ya +91 70166 28865 par call kar sakte hain.",
    "hindi": "\n\nआगे की सहायता के लिए, आप sales@probidconsultants.com पर ईमेल कर सकते हैं या +91 70166 28865 पर कॉल कर सकते हैं।",
}
_HELP_PHRASES = (
    # Language flagged as Hindlish / user follows up about getting human help
    "talk to", "speak to", "get in touch", "reach out", "speak with",
    "talk with", "human", "agent", "representative", "customer care", "help me",
    "help us", "need help", "need your help", "please help", "madad", "help chahiye",
    "help karo", "help karna", "madad chahiye", "contact number", "phone number",
    "mobile number", "mobile no", "phone no", "telephone", "contact details",
    "contact info", "contact probi", "call probi", "your number", "company number",
    "call you", "reach you", "reach us", "contact you", "contact us",
    "moblie", "mobail", "contect", "number dijiye", "number batao", "number bataye",
    "मोबाइल नंबर",
    "email address", "email id", "mail id", "call me", "call us", "call karo",
    "call karna", "insaan se baat", "baat karni hai", "baat karna hai",
    "team se baat", "kisi se baat", "sampark karo", "sampark karna",
    "मदद", "मदद चाहिए", "सहायता", "संपर्क", "बात करनी है", "बात करना है",
)


def wants_contact(question: str) -> bool:
    if not question:
        return False
    q = question.lower().strip()
    return any(p in q for p in _HELP_PHRASES)


# -------------------------------------------------------------------
# Deterministic contact answer — official company contact details.
# Contact questions bypass retrieval/LLM so the number is ALWAYS given.
# -------------------------------------------------------------------
CONTACT_ANSWERS = {
    "english": "You can contact ProBid Consultants LLP at **+91 70166 28865** or email us at **sales@probidconsultants.com**. Our team will be happy to help you with government tenders and GeM portal services.",
    "hinglish": "Aap ProBid Consultants LLP se **+91 70166 28865** par sampark kar sakte hain ya **sales@probidconsultants.com** par email kar sakte hain. Hamari team sarkari tender aur GeM portal services me aapki madad karegi.",
    "hindi": "आप ProBid Consultants LLP से **+91 70166 28865** पर संपर्क कर सकते हैं या **sales@probidconsultants.com** पर ईमेल कर सकते हैं। हमारी टीम सरकारी टेंडर और GeM पोर्टल सेवाओं में आपकी सहायता करेगी।",
}


def answer_contact(question: str) -> str:
    """Return the official contact answer in the user's language."""
    lang = detect_language(question) if question else "english"
    return CONTACT_ANSWERS.get(lang, CONTACT_ANSWERS["english"])


async def generate_answer(
    question: str,
    reranked: list[dict],
    history: list,
    model: str | None = None,
):
    # Build context block only if we have chunks
    if reranked:
        context = "\n\n".join(
            f"[{i + 1}] {c['text']}"
            for i, c in enumerate(reranked)
        )
    else:
        context = ""

    # Check if this is a greeting or general question
    question_lower = question.lower().strip()
    greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'hola', 'namaste',
                 'नमस्ते', 'हाय', 'हेलो', 'प्रणाम', 'हैलो']
    general_questions = ['what is this', 'what are you', 'who are you', 'how can you help', 'what do you do', 'help me',
                        'यह क्या है', 'आप कौन हैं', 'आप क्या करते हैं', 'मदद']
    
    is_greeting = any(question_lower == g or question_lower.startswith(g + ' ') or question_lower.startswith(g + ',') for g in greetings)
    is_general = any(q in question_lower for q in general_questions)
    
    # Detect the user's language style and instruct accordingly
    language = detect_language(question)
    if language == "hindi":
        lang_instruction = "Respond in Hindi (Devanagari script, e.g. नमस्ते), mirroring the user's language."
    elif language == "hinglish":
        lang_instruction = "Respond in Hinglish — same style as the user (Hindi spoken in English/Roman letters, e.g. 'Mujhe tender ke bare me jankari chahiye'). Keep the tone friendly and natural."
    else:
        lang_instruction = "Respond in English."
    
    if is_greeting or (is_general and len(question_lower.split()) < 8):
        # For greetings and general questions, no context needed
        user_message = f"""Question: {question}

{lang_instruction}
Introduce yourself as an assistant for Probid Consultancy LLP who helps with government tenders."""
    elif not context:
        # No context available but not a greeting - general response
        user_message = f"""Question: {question}

{lang_instruction}
Provide helpful information about government tenders and tender processes. Be conversational and offer to help with specific questions."""
    else:
        # For specific questions, use full context from documents
        user_message = f"""<context>
{context}
</context>

Question: {question}

IMPORTANT Instructions:
1. {lang_instruction}
2. Be CONCISE — answer ONLY what is asked, don't add extra details
3. For lists, include EVERY item from context
4. NEVER write citation markers or source numbers like [1], [2] in your answer
5. Use clean formatting: "1." for steps, "- " for bullets, **bold** for key terms

The context documents above are in English, but your ANSWER must be in the user's own language/style. Do not copy the document language.

Answer (in the user's language):"""

    messages = [{"role": "system", "content": get_system_prompt()}]
    for m in history[-4:]:                       # shorter history for 2B
        if m.get("role") in ("user", "assistant"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message})

    model = model or settings.LLM_MODEL

    sources = [
        {
            "id": i + 1,
            "chunk_id": c["chunk_id"],
            "title": c["title"],
            "url": c["url"],
            "page": c.get("page_number"),
            "score": c["rerank_score"],
        }
        for i, c in enumerate(reranked)
    ]

    async def stream():
        try:
            async for token in stream_chat_completions(
                messages,
                model=model,
                temperature=0.2,
                max_tokens=settings.LLM_MAX_TOKENS,
            ):
                yield token
            yield CONTACT_LINES.get(language, CONTACT_LINES["english"])
        except Exception as e:
            yield f"\n\n[Error: {e}]"

    return stream(), sources, model