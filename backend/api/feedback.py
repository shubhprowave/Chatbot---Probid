from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from db.postgres import get_db
from db.models import Feedback
import uuid

router = APIRouter()

class FeedbackRequest(BaseModel):
    message_id: str
    rating: int = Field(..., ge=-1, le=1)
    comment: str | None = None

@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest, db: AsyncSession = Depends(get_db)):
    db.add(Feedback(
        message_id=uuid.UUID(req.message_id),
        rating=req.rating,
        comment=req.comment,
    ))
    await db.commit()
    return {"status": "ok"}