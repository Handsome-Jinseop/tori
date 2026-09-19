from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.audit import write_audit_log
from app.core.ids import new_id
from app.core.security import get_current_admin
from app.core.serialize import doc_out, docs_out
from app.core.time import next_period_start, period_bounds, period_label
from app.db import get_database
from app.routers.admin_rates import current_min_wage
from app.routers.admin_settings import get_settings_doc

router = APIRouter(prefix="/api/admin/employees", tags=["admin-employees"], dependencies=[Depends(get_current_admin)])


async def _face_status_summary(employee_id: str) -> dict:
    db = get_database()
    rows = await db.face_enrollments.find({"employee_id": employee_id}).to_list(length=100)
    devices = {d["_id"]: d async for d in db.devices.find({})}
    out = {}
    for r in rows:
        device = devices.get(r["device_id"])
        store_id = device["store_id"] if device else None
        if store_id:
            out[store_id] = r["status"]
    return out


async def _face_enrollment_details(employee_id: str) -> list[dict]:
    db = get_database()
    rows = await db.face_enrollments.find({"employee_id": employee_id}).to_list(length=100)
    devices = {d["_id"]: d async for d in db.devices.find({})}
    stores = {s["_id"]: s async for s in db.stores.find({})}
    out = []
    for r in rows:
        device = devices.get(r["device_id"])
        store = stores.get(device["store_id"]) if device else None
        d = doc_out(r)
        d["store_id"] = device["store_id"] if device else None
        d["store_name"] = store["name"] if store else "알 수 없는 매장"
        out.append(d)
    return out


@router.get("")
async def list_employees(
    q: str = "",
    employment_type: str = "",
    active: str = "",
    pay_store_id: str = "",
):
    db = get_database()
    query: dict = {}
    if q:
        query["name"] = {"$regex": q, "$options": "i"}
    if employment_type:
        query["employment_type"] = employment_type
    if active == "true":
        query["active"] = True
    elif active == "false":
        query["active"] = False
    if pay_store_id:
        query["pay_store_id"] = pay_store_id

    employees = await db.employees.find(query).sort("name", 1).to_list(length=2000)
    today = date.today().isoformat()
    out = []
    for e in employees:
        d = doc_out(e)
        rate = await db.pay_rates.find_one(
            {"employee_id": e["_id"], "effective_from": {"$lte": today}}, sort=[("effective_from", -1)]
        )
        d["current_pay_rate"] = doc_out(rate)
        d["face_status"] = await _face_status_summary(e["_id"])
        out.append(d)
    return out


class CreateEmployeeBody(BaseModel):
    name: str
    employment_type: str
    pay_store_id: str
    work_store_ids: list[str]
    hire_date: str
    face_exempt: bool = False
    hourly_wage: int | None = None
    monthly_wage: int | None = None


@router.post("")
async def create_employee(body: CreateEmployeeBody, admin=Depends(get_current_admin)):
    from app.core.time import now_utc

    db = get_database()
    employee_id = new_id()
    employee = {
        "_id": employee_id,
        "name": body.name,
        "employment_type": body.employment_type,
        "pay_store_id": body.pay_store_id,
        "work_store_ids": body.work_store_ids,
        "active": True,
        "hire_date": body.hire_date,
        "face_exempt": body.face_exempt,
        "created_at": now_utc(),
    }
    await db.employees.insert_one(employee)
    await db.pay_rates.insert_one(
        {
            "_id": new_id(),
            "employee_id": employee_id,
            "effective_from": body.hire_date,
            "hourly_wage": body.hourly_wage,
            "monthly_wage": body.monthly_wage,
            "weekly_holiday_pay": False,
            "night_premium": False,
            "holiday_premium": False,
            "insurance_national_pension": False,
            "insurance_health": False,
            "insurance_employment": False,
            "created_at": now_utc(),
        }
    )
    await write_audit_log(
        actor=admin["_id"], action="create", target_type="employee", target_id=employee_id,
        after=doc_out(employee), summary=f"직원 '{body.name}' 추가",
    )
    return doc_out(employee)


@router.get("/{employee_id}")
async def get_employee(employee_id: str):
    db = get_database()
    employee = await db.employees.find_one({"_id": employee_id})
    if not employee:
        raise HTTPException(404, "직원을 찾을 수 없어요.")
    d = doc_out(employee)
    today = date.today().isoformat()
    rate = await db.pay_rates.find_one(
        {"employee_id": employee_id, "effective_from": {"$lte": today}}, sort=[("effective_from", -1)]
    )
    d["current_pay_rate"] = doc_out(rate)
    upcoming = await db.pay_rates.find_one(
        {"employee_id": employee_id, "effective_from": {"$gt": today}}, sort=[("effective_from", 1)]
    )
    d["upcoming_pay_rate"] = doc_out(upcoming)
    d["face_status"] = await _face_status_summary(employee_id)
    d["face_enrollments"] = await _face_enrollment_details(employee_id)
    return d


class UpdateEmployeeBody(BaseModel):
    name: str
    work_store_ids: list[str]
    face_exempt: bool


@router.put("/{employee_id}")
async def update_employee(employee_id: str, body: UpdateEmployeeBody, admin=Depends(get_current_admin)):
    db = get_database()
    before = await db.employees.find_one({"_id": employee_id})
    if not before:
        raise HTTPException(404, "직원을 찾을 수 없어요.")
    await db.employees.update_one({"_id": employee_id}, {"$set": body.model_dump()})
    after = await db.employees.find_one({"_id": employee_id})
    await write_audit_log(
        actor=admin["_id"], action="update", target_type="employee", target_id=employee_id,
        before=doc_out(before), after=doc_out(after), summary=f"직원 '{body.name}' 정보 수정",
    )
    return doc_out(after)


@router.post("/{employee_id}/resign")
async def resign_employee(employee_id: str, admin=Depends(get_current_admin)):
    db = get_database()
    employee = await db.employees.find_one({"_id": employee_id})
    if not employee:
        raise HTTPException(404, "직원을 찾을 수 없어요.")
    from app.core.time import now_utc

    await db.employees.update_one(
        {"_id": employee_id}, {"$set": {"active": False, "resigned_at": now_utc()}}
    )
    await db.face_enrollments.update_many(
        {"employee_id": employee_id, "status": "approved"}, {"$set": {"status": "revoked"}}
    )
    await write_audit_log(
        actor=admin["_id"], action="resign", target_type="employee", target_id=employee_id,
        summary=f"직원 '{employee['name']}' 퇴사 처리",
    )
    return doc_out(await db.employees.find_one({"_id": employee_id}))


# --- pay rates ---


@router.get("/{employee_id}/pay-rates")
async def list_pay_rates(employee_id: str):
    db = get_database()
    rows = await db.pay_rates.find({"employee_id": employee_id}).sort("effective_from", -1).to_list(length=200)
    return docs_out(rows)


class PayRateChangeBody(BaseModel):
    hourly_wage: int | None = None
    monthly_wage: int | None = None
    weekly_holiday_pay: bool = False
    night_premium: bool = False
    holiday_premium: bool = False
    insurance_national_pension: bool = False
    insurance_health: bool = False
    insurance_employment: bool = False
    apply_from: str  # "current" | "next"
    confirm_below_min_wage: bool = False


@router.post("/{employee_id}/pay-rates")
async def change_pay_rate(employee_id: str, body: PayRateChangeBody, admin=Depends(get_current_admin)):
    from app.core.time import now_utc

    db = get_database()
    employee = await db.employees.find_one({"_id": employee_id})
    if not employee:
        raise HTTPException(404, "직원을 찾을 수 없어요.")
    settings = await get_settings_doc()
    start_day = settings["default_period_start_day"]
    today = date.today()
    cur_start, cur_end = period_bounds(today, start_day)

    if body.hourly_wage is not None:
        min_wage = await current_min_wage(cur_start.isoformat())
        if body.hourly_wage < min_wage and not body.confirm_below_min_wage:
            raise HTTPException(
                409,
                {"code": "below_min_wage", "min_wage": min_wage, "message": f"최저시급({min_wage}원)보다 낮아요."},
            )

    if body.apply_from == "current":
        confirmed = await db.payrolls.find_one(
            {"employee_id": employee_id, "period_label": period_label(cur_start, cur_end), "status": "confirmed"}
        )
        if confirmed:
            raise HTTPException(400, "이번 정산 기간은 이미 확정됐어요. 다음 정산 기간부터로 적용해 주세요.")
        effective_from = cur_start.isoformat()
    else:
        effective_from = next_period_start(start_day).isoformat()

    doc = {
        "_id": new_id(),
        "employee_id": employee_id,
        "effective_from": effective_from,
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
    await db.pay_rates.insert_one(doc)
    await write_audit_log(
        actor=admin["_id"], action="pay_rate_change", target_type="employee", target_id=employee_id,
        after=doc_out(doc), summary=f"'{employee['name']}' 급여 설정 변경 ({effective_from}부터)",
    )
    return doc_out(doc)


@router.get("/{employee_id}/pay-rates/preview")
async def preview_pay_rate(employee_id: str, hourly_wage: int = Query(...)):
    db = get_database()
    settings = await get_settings_doc()
    start_day = settings["default_period_start_day"]
    today = date.today()
    cur_start, cur_end = period_bounds(today, start_day)

    current_rate = await db.pay_rates.find_one(
        {"employee_id": employee_id, "effective_from": {"$lte": today.isoformat()}}, sort=[("effective_from", -1)]
    )
    old_wage = (current_rate or {}).get("hourly_wage") or await current_min_wage(cur_start.isoformat())

    shifts = await db.shifts.find(
        {
            "employee_id": employee_id,
            "business_date": {"$gte": cur_start.isoformat(), "$lte": cur_end.isoformat()},
            "deleted": {"$ne": True},
        }
    ).to_list(length=5000)
    minutes = 0
    for s in shifts:
        if s.get("check_out"):
            minutes += (s["check_out"] - s["check_in"]).total_seconds() / 60
    before = round(minutes / 60 * old_wage)
    after = round(minutes / 60 * hourly_wage)
    return {
        "period_label": period_label(cur_start, cur_end),
        "hours": round(minutes / 60, 1),
        "before": before,
        "after": after,
        "diff": after - before,
    }


# --- transfers / assignments ---


@router.get("/{employee_id}/assignments")
async def list_assignments(employee_id: str):
    db = get_database()
    rows = await db.assignments.find({"employee_id": employee_id}).sort("effective_from", -1).to_list(length=200)
    return docs_out(rows)


@router.delete("/{employee_id}/assignments/{assignment_id}")
async def cancel_assignment(employee_id: str, assignment_id: str, admin=Depends(get_current_admin)):
    db = get_database()
    assignment = await db.assignments.find_one({"_id": assignment_id, "employee_id": employee_id})
    if not assignment:
        raise HTTPException(404, "이동 예약을 찾을 수 없어요.")
    if assignment.get("applied"):
        raise HTTPException(400, "이미 적용된 이동은 취소할 수 없어요.")
    await db.assignments.delete_one({"_id": assignment_id})
    employee = await db.employees.find_one({"_id": employee_id})
    work_stores = set(employee.get("work_store_ids", []))
    still_used = await db.assignments.find_one(
        {"employee_id": employee_id, "pay_store_id": assignment["pay_store_id"], "applied": {"$ne": True}}
    )
    if not still_used and assignment["pay_store_id"] != employee["pay_store_id"]:
        work_stores.discard(assignment["pay_store_id"])
        await db.employees.update_one({"_id": employee_id}, {"$set": {"work_store_ids": list(work_stores)}})
    await write_audit_log(
        actor=admin["_id"], action="cancel_transfer", target_type="employee", target_id=employee_id,
        summary="이동 예약 취소",
    )
    return {"ok": True}


class TransferBody(BaseModel):
    new_pay_store_id: str
    reason: str
    keep_previous_store: bool


@router.post("/{employee_id}/transfer")
async def transfer_employee(employee_id: str, body: TransferBody, admin=Depends(get_current_admin)):
    from app.core.time import now_utc

    db = get_database()
    employee = await db.employees.find_one({"_id": employee_id})
    if not employee:
        raise HTTPException(404, "직원을 찾을 수 없어요.")
    settings = await get_settings_doc()
    effective_from = next_period_start(settings["default_period_start_day"]).isoformat()

    assignment = {
        "_id": new_id(),
        "employee_id": employee_id,
        "pay_store_id": body.new_pay_store_id,
        "effective_from": effective_from,
        "reason": body.reason,
        "previous_pay_store_id": employee["pay_store_id"],
        "keep_previous_store": body.keep_previous_store,
        "created_at": now_utc(),
        "applied": False,
    }
    await db.assignments.insert_one(assignment)

    work_stores = set(employee.get("work_store_ids", []))
    work_stores.add(body.new_pay_store_id)
    if not body.keep_previous_store:
        work_stores.discard(employee["pay_store_id"])
    await db.employees.update_one(
        {"_id": employee_id}, {"$set": {"work_store_ids": list(work_stores)}}
    )
    if not body.keep_previous_store:
        await db.face_enrollments.update_many(
            {
                "employee_id": employee_id,
                "status": "approved",
                "device_id": {"$in": [d["_id"] async for d in db.devices.find({"store_id": employee["pay_store_id"]})]},
            },
            {"$set": {"status": "revoked"}},
        )

    await write_audit_log(
        actor=admin["_id"], action="transfer", target_type="employee", target_id=employee_id,
        after=doc_out(assignment), summary=f"'{employee['name']}' 이동 예약 ({effective_from}부터)",
    )
    return doc_out(assignment)
