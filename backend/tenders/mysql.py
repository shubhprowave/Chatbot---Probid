"""Read-only access to the external MySQL tender database (live + fresh tenders)."""
import asyncio
import html
import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from config import settings

log = logging.getLogger(__name__)


VIEW_NAME = "all_tenders"

VIEW_DDL = f"""
CREATE OR REPLACE VIEW {VIEW_NAME} AS
SELECT 'live' AS source, ourrefno, TenderNo, purfromdate, submitdate, bid_submission_time,
       opendate, tender_opening_time, bid_submission_start_date, Document_start_date, Document_end_date,
       ContractType, BidValidity, tenderamount, earnestamount, doccost, org_name,
       CONVERT(address USING utf8mb4) AS address, Work, state_name, city, dt,
       tendertype, form_of_contract, pincode, sector, link
FROM live_tenders
UNION ALL
SELECT 'fresh' AS source, ourrefno, TenderNo, purfromdate, submitdate, bid_submission_time,
       opendate, tender_opening_time, bid_submission_start_date, Document_start_date, Document_end_date,
       ContractType, BidValidity, tenderamount, earnestamount, doccost, org_name,
       CONVERT(address USING utf8mb4) AS address, Work, state_name, city, dt,
       tendertype, form_of_contract, pincode, sector, link
FROM fresh_tenders
"""


def _connect() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=settings.MYSQL_DB,
        charset="utf8mb4",
        cursorclass=DictCursor,
        connect_timeout=5,
        read_timeout=20,
        write_timeout=20,
        autocommit=True,
    )


def _ensure_view_sync() -> None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW FULL TABLES LIKE %s", (VIEW_NAME,))
            if cur.fetchone():
                return
            cur.execute(VIEW_DDL)
    log.info("[tender] created view %s", VIEW_NAME)


def _run_sync(sql: str, limit: int) -> list[dict[str, Any]]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return list(cur.fetchmany(limit))


def _run_count_sync(sql: str) -> int:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            if not row:
                return 0
            return int(next(iter(row.values())) or 0)


async def ensure_view() -> None:
    await asyncio.to_thread(_ensure_view_sync)


async def run_query(sql: str, limit: int | None = None) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_run_sync, sql, limit or settings.TENDER_RESULT_LIMIT)


async def run_count(sql: str) -> int:
    return await asyncio.to_thread(_run_count_sync, sql)


def _to_display(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}"
    if isinstance(value, Decimal):
        return str(value)
    return value


def format_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map a raw DB row to the fields shown in the chatbot table."""
    def clean(v: Any) -> Any:
        return html.unescape(v) if isinstance(v, str) else v

    description = " ".join(str(clean(row.get("Work")) or "").split())
    return {
        "pbid": row.get("ourrefno"),
        "tender_no": row.get("TenderNo"),
        "description": description,
        "agency": clean(row.get("org_name")),
        "state": clean(row.get("state_name")),
        "city": clean(row.get("city")),
        "value": _to_display(row.get("tenderamount")),
        "due_date": _to_display(row.get("submitdate")),
        "open_date": _to_display(row.get("opendate")),
        "source": row.get("source"),
        "link": row.get("link"),
    }
