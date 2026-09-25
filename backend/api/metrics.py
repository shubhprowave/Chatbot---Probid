from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from db.postgres import get_db
from api.admin import require_admin
from analytics import queries as q

router = APIRouter(prefix="/admin/metrics", dependencies=[Depends(require_admin)])


@router.get("/overview")
async def overview(
    tenant_id: str = "default",
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
):
    return await q.overview_stats(db, tenant_id, hours)


@router.get("/timeseries")
async def timeseries(
    tenant_id: str = "default",
    hours: int = Query(24, ge=1, le=720),
    bucket: str = Query("hour", pattern="^(hour|day)$"),
    db: AsyncSession = Depends(get_db),
):
    return await q.timeseries(db, tenant_id, hours, bucket)


@router.get("/latency")
async def latency(
    tenant_id: str = "default",
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
):
    return await q.latency_histogram(db, tenant_id, hours)


@router.get("/top-questions")
async def top_questions(
    tenant_id: str = "default",
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    return await q.top_questions(db, tenant_id, limit)


@router.get("/unanswered")
async def unanswered(
    tenant_id: str = "default",
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    return await q.unanswered_questions(db, tenant_id, limit)