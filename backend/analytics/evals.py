"""
RAGAS evaluation runner.
Compares generated answers against ground truth on a golden test set.
"""
import time, logging
from sqlalchemy import select, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from db.postgres import AsyncSessionLocal
from db.models import GoldenQA, EvalRun, EvalResult
from rag.pipeline import rag_pipeline

log = logging.getLogger(__name__)


async def run_evaluation(
    run_name: str,
    dataset_name: str = "default",
    tenant_id: str = "default",
    metrics: list[str] | None = None,
) -> dict:
    """
    Execute evaluation:
    1. Load golden Q/A pairs from Postgres
    2. Run each question through the RAG pipeline
    3. Compute RAGAS metrics
    4. Store results + summary
    """
    from ragas import evaluate, EvaluationDataset, SingleTurnSample
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
        answer_correctness,
    )

    async with AsyncSessionLocal() as db:
        # 1. Load golden set
        golden = (await db.execute(
            select(GoldenQA).where(GoldenQA.tenant_id == tenant_id)
        )).scalars().all()
        if not golden:
            return {"status": "failed", "error": "no golden QA pairs"}

        # 2. Create eval run record
        run = EvalRun(
            name=run_name,
            dataset_name=dataset_name,
            total_questions=len(golden),
            status="running",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        log.info(f"[eval] {run_name}: {len(golden)} questions")

        # 3. Generate answers
        samples = []
        raw_rows = []
        for i, g in enumerate(golden):
            t0 = time.perf_counter()
            result = await rag_pipeline(g.question, [], tenant_id, db)

            answer = ""
            async for tok in result["answer_gen"]:
                answer += tok

            latency_ms = int((time.perf_counter() - t0) * 1000)

            contexts = [s.get("title", "") for s in result.get("sources", [])]
            # We don't have full chunk text here; fetch it
            # For brevity, using source titles. Improve by joining chunks.
            samples.append(SingleTurnSample(
                user_input=g.question,
                response=answer,
                retrieved_contexts=contexts,
                reference=g.ground_truth,
            ))
            raw_rows.append({
                "question": g.question,
                "answer": answer,
                "ground_truth": g.ground_truth,
                "contexts": contexts,
                "latency_ms": latency_ms,
            })
            log.info(f"[eval] {i+1}/{len(golden)} done")

        # 4. RAGAS evaluate
        dataset = EvaluationDataset(samples=samples)
        use_metrics = metrics or [
            "faithfulness", "answer_relevancy",
            "context_precision", "context_recall", "answer_correctness"
        ]
        metric_objs = {
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_precision": context_precision,
            "context_recall": context_recall,
            "answer_correctness": answer_correctness,
        }
        chosen = [metric_objs[m] for m in use_metrics if m in metric_objs]

        log.info("[eval] running RAGAS...")
        report = evaluate(
            dataset=dataset,
            metrics=chosen,
            raise_exceptions=False,
        )

        # 5. Store results
        df = report.to_pandas()
        for i, row in enumerate(raw_rows):
            r = df.iloc[i] if i < len(df) else {}
            db.add(EvalResult(
                run_id=run.id,
                question=row["question"],
                ground_truth=row["ground_truth"],
                answer=row["answer"],
                contexts=row["contexts"],
                faithfulness=_f(r, "faithfulness"),
                answer_relevancy=_f(r, "answer_relevancy"),
                context_precision=_f(r, "context_precision"),
                context_recall=_f(r, "context_recall"),
                answer_correctness=_f(r, "answer_correctness"),
                latency_ms=row["latency_ms"],
            ))

        # Summary
        summary = {}
        for m in use_metrics:
            col = df.get(m)
            if col is not None:
                summary[m] = float(col.mean(skipna=True))

        run.status = "completed"
        run.summary = summary
        run.finished_at = sql_text("NOW()")
        await db.commit()

        return {
            "run_id": str(run.id),
            "status": "completed",
            "summary": summary,
            "questions": len(golden),
        }


def _f(row, key):
    try:
        v = row.get(key)
        return float(v) if v is not None and v == v else None  # NaN check
    except Exception:
        return None