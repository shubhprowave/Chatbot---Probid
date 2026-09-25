"""
Cost tracking. Self-hosted = $0 runtime; we still track "what-if" costs
so you can compare against paid APIs.
"""
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

# Approximate self-hosted cost per 1M tokens (amortized VPS + electricity)
SELF_HOSTED_COST_PER_1M_TOKENS = 0.02   # ~₹1,700/mo VPS + power

# Reference cloud pricing (for comparison)
CLOUD_PRICING = {
    "groq_llama_70b":     {"in": 0.59, "out": 0.79},   # per 1M tokens
    "openai_gpt4o_mini":  {"in": 0.15, "out": 0.60},
    "gemini_1_5_flash":   {"in": 0.075, "out": 0.30},
    "anthropic_haiku":    {"in": 0.25, "out": 1.25},
}


async def cost_summary(db: AsyncSession, tenant_id: str, days: int = 30) -> dict:
    q = sql_text("""
    SELECT
      COUNT(*) AS answers,
      COALESCE(SUM(tokens_in), 0)  AS total_in,
      COALESCE(SUM(tokens_out), 0) AS total_out,
      COALESCE(SUM(cost_usd), 0)   AS actual_cost
    FROM messages m
    JOIN conversations c ON c.id = m.conversation_id
    WHERE c.tenant_id = :tenant_id
      AND m.role = 'assistant'
      AND m.created_at >= NOW() - INTERVAL '1 day' * :days;
    """)
    row = (await db.execute(q, {"tenant_id": tenant_id, "days": days})).mappings().one()

    total_in = int(row["total_in"] or 0)
    total_out = int(row["total_out"] or 0)

    comparison = {}
    for name, price in CLOUD_PRICING.items():
        cost = (total_in / 1_000_000) * price["in"] + (total_out / 1_000_000) * price["out"]
        comparison[name] = round(cost, 4)

    self_hosted = (
        (total_in + total_out) / 1_000_000
    ) * SELF_HOSTED_COST_PER_1M_TOKENS

    return {
        "days": days,
        "answers": int(row["answers"] or 0),
        "tokens_in": total_in,
        "tokens_out": total_out,
        "tokens_total": total_in + total_out,
        "actual_cost_usd": round(float(row["actual_cost"] or 0) + self_hosted, 4),
        "comparison_cloud_usd": comparison,
        "savings_vs_gpt4o_mini": round(
            comparison.get("openai_gpt4o_mini", 0) - self_hosted, 4
        ),
    }