from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.audit import write_audit_log
from app.core.ids import new_id
from app.core.security import get_current_admin
from app.core.serialize import doc_out, docs_out
from app.core.time import business_date_for, now_utc, parse_iso
from app.db import get_database

router = APIRouter(prefix="/api/admin/shifts", tags=["admin-shifts"], dependencies=[Depends(get_current_admin)])


async def _confirmed_payroll_for(employee_id: str, business_date: str) -> dict | None:
    db = get_database()
    async for p in db.payrolls.find({"employee_id": employee_id, "status": "confirmed"}):
        if p["period_start"] <= business_date <= p["period_end"]:
            return p
    return None


async def _enrich(rows: list[dict]) -> list[dict]:
    db = get_database()
    emp_ids = {r["employee_id"] for r in rows}
    store_ids = {r["store_id"] for r in rows}
    employees = {e["_id"]: e async for e in db.employees.find({"_id": {"$in": list(emp_ids)}})}
    stores = {s["_id"]: s async for s in db.stores.find({"_id": {"$in": list(store_ids)}})}
    out = []
    for r in rows:
        d = doc_out(r)
        emp = employees.get(r["employee_id"])
        d["employee_name"] = emp["name"] if emp else "(임시 등록)"
        d["employment_type"] = emp.get("employment_type") if emp else "part_time"
        d["store_name"] = stores.get(r["store_id"], {}).get("name", "-")
        if r.get("check_out"):
            d["minutes"] = round((r["check_out"] - r["check_in"]).total_seconds() / 60)
        else:
            d["minutes"] = None
        out.append(d)
    return out


@router.get("")
async def list_shifts(
    store_id: str = "",
    employee_id: str = "",
    date_from: str = "",
    date_to: str = "",
    status: str = "",
    has_flags: str = "",
    flag: str = "",
    flags_any: str = "",
    reviewed: str = "",
    limit: int = 500,
):
    db = get_database()
    query: dict = {"deleted": {"$ne": True}}
    if store_id:
        query["store_id"] = store_id
    if employee_id:
        query["employee_id"] = employee_id
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        query["business_date"] = rng
    if status:
        query["status"] = status
    if has_flags == "true":
        query["flags.0"] = {"$exists": True}
    if flag:
        query["flags"] = flag
    if flags_any:
        query["flags"] = {"$in": flags_any.split(",")}
    if reviewed == "true":
        query["reviewed"] = True
    elif reviewed == "false":
        query["reviewed"] = {"$ne": True}

    rows = await db.shifts.find(query).sort("check_in", -1).to_list(length=limit)
    enriched = await _enrich(rows)
    total_minutes = sum(r["minutes"] or 0 for r in enriched)
    return {"items": enriched, "total_minutes": total_minutes}


@router.get("/{shift_id}")
async def get_shift(shift_id: str):
    db = get_database()
    row = await db.shifts.find_one({"_id": shift_id})
    if not row:
        raise HTTPException(404, "근무 기록을 찾을 수 없어요.")
    d = (await _enrich([row]))[0]
    events = await db.attendance_events.find(
        {"employee_id": row["employee_id"], "recorded_at": {
            "$gte": row["check_in"], "$lte": row.get("check_out") or now_utc()
        }}
    ).sort("recorded_at", 1).to_list(length=20)
    d["raw_events"] = docs_out(events)
    locked = await _confirmed_payroll_for(row["employee_id"], row["business_date"])
    d["locked_payroll_id"] = locked["_id"] if locked else None
    return d


class ShiftUpdateBody(BaseModel):
    store_id: str
    check_in: str
    check_out: str | None = None
    memo: str = ""
    reason: str = ""


@router.put("/{shift_id}")
async def update_shift(shift_id: str, body: ShiftUpdateBody, admin=Depends(get_current_admin)):
    db = get_database()
    before = await db.shifts.find_one({"_id": shift_id})
    if not before:
        raise HTTPException(404, "근무 기록을 찾을 수 없어요.")
    locked = await _confirmed_payroll_for(before["employee_id"], before["business_date"])
    if locked:
        raise HTTPException(409, "이 근무는 확정된 정산에 포함돼 있어요. 수정하려면 정산을 재오픈해야 해요.")

    check_in = parse_iso(body.check_in)
    check_out = parse_iso(body.check_out) if body.check_out else None
    new_business_date = business_date_for(check_in)

    history_entry = {
        "at": now_utc(),
        "by": admin["_id"],
        "reason": body.reason,
        "before": {"check_in": before["check_in"], "check_out": before.get("check_out"), "store_id": before["store_id"]},
        "after": {"check_in": check_in, "check_out": check_out, "store_id": body.store_id},
    }
    flags = list(before.get("flags", []))
    if "manual_edit" not in flags:
        flags.append("manual_edit")

    await db.shifts.update_one(
        {"_id": shift_id},
        {
            "$set": {
                "store_id": body.store_id,
                "check_in": check_in,
                "check_out": check_out,
                "status": "closed" if check_out else "open",
                "business_date": new_business_date,
                "memo": body.memo,
                "flags": flags,
                "reviewed": False,
            },
            "$push": {"history": history_entry},
        },
    )
    after = await db.shifts.find_one({"_id": shift_id})
    await write_audit_log(
        actor=admin["_id"], action="update", target_type="shift", target_id=shift_id,
        before=doc_out(before), after=doc_out(after), summary=f"근무 기록 수정: {body.reason or '(사유 없음)'}",
    )
    return (await _enrich([after]))[0]


class ShiftCreateBody(BaseModel):
    employee_id: str
    store_id: str
    check_in: str
    check_out: str | None = None
    reason: str = ""


@router.post("")
async def create_shift(body: ShiftCreateBody, admin=Depends(get_current_admin)):
    db = get_database()
    check_in = parse_iso(body.check_in)
    check_out = parse_iso(body.check_out) if body.check_out else None
    doc = {
        "_id": new_id(),
        "employee_id": body.employee_id,
        "store_id": body.store_id,
        "business_date": business_date_for(check_in),
        "check_in": check_in,
        "check_out": check_out,
        "status": "closed" if check_out else "open",
        "flags": ["manual_add"],
        "memo": "",
        "history": [{"at": now_utc(), "by": admin["_id"], "reason": body.reason, "before": None, "after": "생성"}],
        "reviewed": False,
        "deleted": False,
    }
    await db.shifts.insert_one(doc)
    await write_audit_log(
        actor=admin["_id"], action="create", target_type="shift", target_id=doc["_id"],
        after=doc_out(doc), summary=f"근무 기록 직접 추가: {body.reason or '(사유 없음)'}",
    )
    return (await _enrich([doc]))[0]


@router.delete("/{shift_id}")
async def delete_shift(shift_id: str, admin=Depends(get_current_admin)):
    db = get_database()
    before = await db.shifts.find_one({"_id": shift_id})
    if not before:
        raise HTTPException(404, "근무 기록을 찾을 수 없어요.")
    locked = await _confirmed_payroll_for(before["employee_id"], before["business_date"])
    if locked:
        raise HTTPException(409, "이 근무는 확정된 정산에 포함돼 있어요. 수정하려면 정산을 재오픈해야 해요.")
    await db.shifts.update_one({"_id": shift_id}, {"$set": {"deleted": True}})
    await write_audit_log(
        actor=admin["_id"], action="delete", target_type="shift", target_id=shift_id,
        before=doc_out(before), summary="근무 기록 삭제",
    )
    return {"ok": True}


class ReviewBody(BaseModel):
    ids: list[str]


@router.post("/review")
async def review_shifts(body: ReviewBody, admin=Depends(get_current_admin)):
    db = get_database()
    await db.shifts.update_many(
        {"_id": {"$in": body.ids}},
        {"$set": {"reviewed": True, "reviewed_at": now_utc(), "reviewed_by": admin["_id"]}},
    )
    await write_audit_log(
        actor=admin["_id"], action="review", target_type="shift", target_id=",".join(body.ids),
        summary=f"근무 기록 {len(body.ids)}건 확인 완료",
    )
    return {"ok": True}
