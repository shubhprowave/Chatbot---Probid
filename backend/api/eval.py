from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from db.postgres import get_db
from db.models import GoldenQA, EvalRun, EvalResult
from api.admin import require_admin
from analytics.evals import run_evaluation
import uuid

router = APIRouter(prefix="/admin/eval", dependencies=[Depends(require_admin)])


class GoldenQAIn(BaseModel):
    question: str
    ground_truth: str
    category: str | None = None
    tenant_id: str = "default"


class EvalRunIn(BaseModel):
    name: str
    dataset_name: str = "default"
    tenant_id: str = "default"
    metrics: list[str] | None = None


@router.get("/golden")
async def list_golden(tenant_id: str = "default", db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(GoldenQA).where(GoldenQA.tenant_id == tenant_id)
        .order_by(desc(GoldenQA.created_at))
    )).scalars().all()
    return [
        {"id": str(r.id), "question": r.question,
         "ground_truth": r.ground_truth, "category": r.category}
        for r in rows
    ]


@router.post("/golden")
async def add_golden(body: GoldenQAIn, db: AsyncSession = Depends(get_db)):
    g = GoldenQA(
        tenant_id=body.tenant_id,
        question=body.question,
        ground_truth=body.ground_truth,
        category=body.category,
    )
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return {"id": str(g.id)}


@router.delete("/golden/{qa_id}")
async def delete_golden(qa_id: str, db: AsyncSession = Depends(get_db)):
    g = (await db.execute(
        select(GoldenQA).where(GoldenQA.id == uuid.UUID(qa_id))
    )).scalar_one_or_none()
    if not g:
        raise HTTPException(404)
    await db.delete(g)
    await db.commit()
    return {"status": "deleted"}


@router.post("/run")
async def start_run(body: EvalRunIn, bg: BackgroundTasks):
    bg.add_task(
        run_evaluation,
        run_name=body.name,
        dataset_name=body.dataset_name,
        tenant_id=body.tenant_id,
        metrics=body.metrics,
    )
    return {"status": "started"}


@router.get("/runs")
async def list_runs(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(EvalRun).order_by(desc(EvalRun.started_at)).limit(50)
    )).scalars().all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "status": r.status,
            "total": r.total_questions,
            "summary": r.summary,
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        } for r in rows
    ]


@router.get("/runs/{run_id}")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    run = (await db.execute(
        select(EvalRun).where(EvalRun.id == uuid.UUID(run_id))
    )).scalar_one_or_none()
    if not run:
        raise HTTPException(404)
    results = (await db.execute(
        select(EvalResult).where(EvalResult.run_id == run.id)
    )).scalars().all()
    return {
        "run": {
            "id": str(run.id), "name": run.name, "status": run.status,
            "summary": run.summary,
            "started_at": run.started_at.isoformat(),
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        },
        "results": [
            {
                "question": r.question,
                "ground_truth": r.ground_truth,
                "answer": r.answer,
                "faithfulness": r.faithfulness,
                "answer_relevancy": r.answer_relevancy,
                "context_precision": r.context_precision,
                "context_recall": r.context_recall,
                "answer_correctness": r.answer_correctness,
                "latency_ms": r.latency_ms,
            } for r in results
        ],
    }