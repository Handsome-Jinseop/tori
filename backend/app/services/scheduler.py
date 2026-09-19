from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.time import KST, UTC, now_utc
from app.db import get_database

logger = logging.getLogger("scheduler")


async def run_auto_checkout() -> int:
    db = get_database()
    now_kst = now_utc().astimezone(KST)
    closed_count = 0

    open_shifts = await db.shifts.find({"status": "open", "deleted": {"$ne": True}}).to_list(length=5000)
    if not open_shifts:
        return 0
    store_ids = {s["store_id"] for s in open_shifts}
    stores = {s["_id"]: s async for s in db.stores.find({"_id": {"$in": list(store_ids)}})}

    for shift in open_shifts:
        store = stores.get(shift["store_id"])
        if not store:
            continue
        business_date = date.fromisoformat(shift["business_date"])
        hh, mm = (int(x) for x in store["close_time"].split(":"))
        close_day = business_date + timedelta(days=1) if store.get("close_next_day") else business_date
        close_dt_kst = datetime(close_day.year, close_day.month, close_day.day, hh, mm, tzinfo=KST)
        deadline = close_dt_kst + timedelta(minutes=store.get("grace_min", 15))
        if now_kst > deadline:
            close_dt_utc = close_dt_kst.astimezone(UTC)
            flags = list(shift.get("flags", []))
            if "auto_checkout" not in flags:
                flags.append("auto_checkout")
            await db.shifts.update_one(
                {"_id": shift["_id"]},
                {"$set": {"check_out": close_dt_utc, "status": "closed", "flags": flags}},
            )
            closed_count += 1
    return closed_count


async def apply_pending_assignments() -> int:
    db = get_database()
    today = date.today().isoformat()
    applied = 0
    async for a in db.assignments.find({"applied": {"$ne": True}, "effective_from": {"$lte": today}}):
        await db.employees.update_one({"_id": a["employee_id"]}, {"$set": {"pay_store_id": a["pay_store_id"]}})
        await db.assignments.update_one({"_id": a["_id"]}, {"$set": {"applied": True}})
        applied += 1
    return applied


async def _tick() -> None:
    try:
        closed = await run_auto_checkout()
        applied = await apply_pending_assignments()
        if closed or applied:
            logger.info("scheduler tick: auto_checkout=%s assignments_applied=%s", closed, applied)
    except Exception:
        logger.exception("scheduler tick failed")


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(_tick, "interval", minutes=5, id="auto_checkout_tick", next_run_time=now_utc())
    scheduler.start()
    return scheduler
