from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.audit import write_audit_log
from app.core.ids import new_id
from app.core.security import get_current_admin
from app.core.serialize import doc_out, docs_out
from app.db import get_database

router = APIRouter(prefix="/api/admin/holidays", tags=["admin-holidays"], dependencies=[Depends(get_current_admin)])


class HolidayBody(BaseModel):
    date: str
    name: str


@router.get("")
async def list_holidays(year: int | None = None):
    db = get_database()
    query = {}
    if year:
        query["date"] = {"$gte": f"{year}-01-01", "$lte": f"{year}-12-31"}
    holidays = await db.holidays.find(query).sort("date", 1).to_list(length=1000)
    return docs_out(holidays)


@router.post("")
async def upsert_holiday(body: HolidayBody, admin=Depends(get_current_admin)):
    db = get_database()
    existing = await db.holidays.find_one({"date": body.date})
    if existing:
        await db.holidays.update_one({"date": body.date}, {"$set": {"name": body.name}})
    else:
        await db.holidays.insert_one({"_id": new_id(), "date": body.date, "name": body.name})
    await write_audit_log(
        actor=admin["_id"], action="upsert", target_type="holiday", target_id=body.date,
        after=body.model_dump(), summary=f"휴일 '{body.date} {body.name}' 등록",
    )
    return doc_out(await db.holidays.find_one({"date": body.date}))


@router.delete("/{holiday_date}")
async def delete_holiday(holiday_date: str, admin=Depends(get_current_admin)):
    db = get_database()
    existing = await db.holidays.find_one({"date": holiday_date})
    if not existing:
        raise HTTPException(404, "휴일을 찾을 수 없어요.")
    await db.holidays.delete_one({"date": holiday_date})
    await write_audit_log(
        actor=admin["_id"], action="delete", target_type="holiday", target_id=holiday_date,
        before=doc_out(existing), summary=f"휴일 '{holiday_date}' 해제",
    )
    return {"ok": True}
