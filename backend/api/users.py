from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession
from db.postgres import get_db
import re

router = APIRouter(prefix="/user")


class LeadIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=7, max_length=20)
    session_id: str = Field("anon", max_length=128)
    tenant_id: str = Field("default", max_length=64)


def _clean_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0"):
        digits = digits[1:]
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits[-10:] if len(digits) > 10 else digits


@router.post("/register", tags=["user"])
async def register_lead(lead: LeadIn, db: AsyncSession = Depends(get_db)):
    """Register a chatbot visitor's name + phone so the sales team can follow up."""
    phone = _clean_phone(lead.phone)
    if not phone or len(phone) < 10:
        raise HTTPException(400, "Please enter a valid phone number (10 digits).")

    result = await db.execute(sql_text(
        """
        INSERT INTO users (tenant_id, name, phone, session_id, last_seen)
        VALUES (:tenant_id, :name, :phone, :session_id, NOW())
        ON CONFLICT (phone) DO UPDATE SET
            name = EXCLUDED.name,
            session_id = EXCLUDED.session_id,
            last_seen = NOW()
        RETURNING id, name, phone
        """
    ), {
        "tenant_id": lead.tenant_id,
        "name": lead.name.strip(),
        "phone": phone,
        "session_id": lead.session_id,
    })
    await db.commit()
    row = result.mappings().first()
    return {
        "ok": True,
        "id": str(row["id"]),
        "name": row["name"],
        "phone": row["phone"],
    }