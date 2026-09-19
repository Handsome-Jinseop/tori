from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.audit import write_audit_log
from app.core.ids import new_id
from app.core.security import get_current_admin
from app.core.serialize import doc_out, docs_out
from app.core.time import now_utc
from app.db import get_database

router = APIRouter(
    prefix="/api/admin/employee-requests",
    tags=["admin-employee-requests"],
    dependencies=[Depends(get_current_admin)],
)


async def _enrich(rows: list[dict]) -> list[dict]:
    db = get_database()
    store_ids = {r["store_id"] for r in rows}
    stores = {s["_id"]: s async for s in db.stores.find({"_id": {"$in": list(store_ids)}})}
    out = []
    for r in rows:
        d = doc_out(r)
        d["store_name"] = stores.get(r["store_id"], {}).get("name", "알 수 없는 매장")
        d["shift_count"] = await db.shifts.count_documents({"employee_id": r["temp_id"]})
        first_shift = await db.shifts.find_one({"employee_id": r["temp_id"]}, sort=[("check_in", 1)])
        d["first_shift_at"] = doc_out(first_shift).get("check_in") if first_shift else None
        out.append(d)
    return out


@router.get("")
async def list_requests(status: str = "pending"):
    db = get_database()
    rows = await db.employee_requests.find({"status": status}).sort("created_at", -1).to_list(length=1000)
    return await _enrich(rows)


class AcceptBody(BaseModel):
    name: str
    employment_type: str  # part_time | regular
    pay_store_id: str
    work_store_ids: list[str]
    hire_date: str
    hourly_wage: int | None = None
    monthly_wage: int | None = None
    weekly_holiday_pay: bool = False
    night_premium: bool = False
    holiday_premium: bool = False
    insurance_national_pension: bool = False
    insurance_health: bool = False
    insurance_employment: bool = False


async def _migrate_temp_records(temp_id: str, employee_id: str) -> None:
    db = get_database()
    await db.shifts.update_many({"employee_id": temp_id}, {"$set": {"employee_id": employee_id}})
    await db.attendance_events.update_many({"employee_id": temp_id}, {"$set": {"employee_id": employee_id}})
    await db.face_enrollments.update_many({"employee_id": temp_id}, {"$set": {"employee_id": employee_id}})


@router.post("/{request_id}/accept")
async def accept_request(request_id: str, body: AcceptBody, admin=Depends(get_current_admin)):
    db = get_database()
    req = await db.employee_requests.find_one({"_id": request_id})
    if not req or req["status"] != "pending":
        raise HTTPException(400, "처리할 수 없는 요청이에요.")

    employee_id = new_id()
    employee = {
        "_id": employee_id,
        "name": body.name,
        "employment_type": body.employment_type,
        "pay_store_id": body.pay_store_id,
        "work_store_ids": body.work_store_ids,
        "active": True,
        "hire_date": body.hire_date,
        "face_exempt": False,
        "created_at": now_utc(),
    }
    await db.employees.insert_one(employee)

    pay_rate = {
        "_id": new_id(),
        "employee_id": employee_id,
        "effective_from": body.hire_date,
        "hourly_wage": body.hourly_wage,
        "monthly_wage": body.monthly_wage,
        "weekly_holiday_pay": body.weekly_holiday_pay,
        "night_premium": body.night_premium,
        "holiday_premium": body.holiday_premium,
        "insurance_national_pension": body.insurance_national_pension,
        "insurance_health": body.insurance_health,
        "insurance_employment": body.insurance_employment,
        "created_at": now_utc(),
    }
    await db.pay_rates.insert_one(pay_rate)

    await _migrate_temp_records(req["temp_id"], employee_id)
    await db.face_enrollments.update_many(
        {"employee_id": employee_id, "status": "pending"},
        {"$set": {"status": "approved", "approved_at": now_utc(), "approver": admin["_id"]}},
    )
    await db.employee_requests.update_one(
        {"_id": request_id},
        {"$set": {
            "status": "accepted", "processed_at": now_utc(), "processor": admin["_id"],
            "linked_employee_id": employee_id,
        }},
    )
    await write_audit_log(
        actor=admin["_id"], action="accept", target_type="employee_request", target_id=request_id,
        after={"employee_id": employee_id}, summary=f"신규 직원 요청 수락 → '{body.name}' 등록",
    )
    return {"employee_id": employee_id}


class LinkBody(BaseModel):
    employee_id: str


@router.post("/{request_id}/link")
async def link_request(request_id: str, body: LinkBody, admin=Depends(get_current_admin)):
    db = get_database()
    req = await db.employee_requests.find_one({"_id": request_id})
    if not req or req["status"] != "pending":
        raise HTTPException(400, "처리할 수 없는 요청이에요.")
    employee = await db.employees.find_one({"_id": body.employee_id})
    if not employee:
        raise HTTPException(404, "직원을 찾을 수 없어요.")

    await _migrate_temp_records(req["temp_id"], body.employee_id)
    await db.face_enrollments.update_many(
        {"employee_id": body.employee_id, "status": "pending"},
        {"$set": {"status": "approved", "approved_at": now_utc(), "approver": admin["_id"]}},
    )
    await db.employee_requests.update_one(
        {"_id": request_id},
        {"$set": {
            "status": "linked", "processed_at": now_utc(), "processor": admin["_id"],
            "linked_employee_id": body.employee_id,
        }},
    )
    await write_audit_log(
        actor=admin["_id"], action="link", target_type="employee_request", target_id=request_id,
        after={"employee_id": body.employee_id},
        summary=f"신규 직원 요청을 기존 직원 '{employee['name']}'에 연결",
    )
    return {"employee_id": body.employee_id}


class RejectBody(BaseModel):
    reason: str = ""


@router.post("/{request_id}/reject")
async def reject_request(request_id: str, body: RejectBody, admin=Depends(get_current_admin)):
    db = get_database()
    req = await db.employee_requests.find_one({"_id": request_id})
    if not req or req["status"] != "pending":
        raise HTTPException(400, "처리할 수 없는 요청이에요.")

    await db.shifts.delete_many({"employee_id": req["temp_id"]})
    await db.attendance_events.delete_many({"employee_id": req["temp_id"]})
    await db.face_enrollments.delete_many({"employee_id": req["temp_id"]})
    await db.employee_requests.update_one(
        {"_id": request_id},
        {"$set": {
            "status": "rejected", "processed_at": now_utc(), "processor": admin["_id"],
            "reject_reason": body.reason,
        }},
    )
    await write_audit_log(
        actor=admin["_id"], action="reject", target_type="employee_request", target_id=request_id,
        summary=f"신규 직원 요청 거절: {body.reason}" if body.reason else "신규 직원 요청 거절",
    )
    return {"ok": True}
