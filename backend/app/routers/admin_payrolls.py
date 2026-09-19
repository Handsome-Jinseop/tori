from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.audit import write_audit_log
from app.core.ids import new_id
from app.core.security import get_current_admin
from app.core.serialize import doc_out, docs_out
from app.core.time import now_utc, period_bounds, period_label as make_period_label
from app.db import get_database
from app.routers.admin_settings import get_settings_doc
from app.services.payroll_engine import compute_employee_payroll, gather_inputs_for_employee

router = APIRouter(prefix="/api/admin/payrolls", tags=["admin-payrolls"], dependencies=[Depends(get_current_admin)])


@router.get("/current-period")
async def current_period():
    settings = await get_settings_doc()
    start, end = period_bounds(date.today(), settings["default_period_start_day"])
    return {"period_start": start.isoformat(), "period_end": end.isoformat(), "period_label": make_period_label(start, end)}


@router.get("/needs-review")
async def needs_review(period_start: str = Query(...), period_end: str = Query(...)):
    db = get_database()
    count = await db.shifts.count_documents({
        "business_date": {"$gte": period_start, "$lte": period_end},
        "flags.0": {"$exists": True},
        "reviewed": {"$ne": True},
        "deleted": {"$ne": True},
    })
    return {"count": count}


@router.get("")
async def get_payrolls(period_start: str = Query(...), period_end: str = Query(...)):
    db = get_database()
    label = f"{period_start}~{period_end}"
    rows = await db.payrolls.find({"period_label": label}).to_list(length=2000)
    employees = {e["_id"]: e async for e in db.employees.find({})}
    out = []
    for r in rows:
        d = doc_out(r)
        emp = employees.get(r["employee_id"], {})
        d["employee_name"] = emp.get("name", "-")
        d["employment_type"] = emp.get("employment_type")
        out.append(d)
    out.sort(key=lambda x: x["employee_name"])

    status = "confirmed" if rows and all(r["status"] == "confirmed" for r in rows) else "draft"
    review_count = await db.shifts.count_documents({
        "business_date": {"$gte": period_start, "$lte": period_end},
        "flags.0": {"$exists": True}, "reviewed": {"$ne": True}, "deleted": {"$ne": True},
    })

    overlapping_confirmed = False
    emp_ids = [r["employee_id"] for r in rows]
    async for p in db.payrolls.find({"employee_id": {"$in": emp_ids}, "status": "confirmed", "period_label": {"$ne": label}}):
        if not (p["period_end"] < period_start or p["period_start"] > period_end):
            overlapping_confirmed = True
            break

    totals = {
        "gross_pay": sum(r["gross_pay"] for r in rows),
        "deduction_total": sum(r["deduction_total"] + r["insurance_total"] for r in rows),
        "net_pay": sum(r["net_pay"] for r in rows),
    }
    store_totals: dict[str, int] = {}
    for r in rows:
        store_totals[r["pay_store_id"]] = store_totals.get(r["pay_store_id"], 0) + r["gross_pay"]

    return {
        "period_start": period_start, "period_end": period_end, "period_label": label,
        "status": status, "items": out, "totals": totals, "store_totals": store_totals,
        "review_count": review_count, "overlapping_confirmed": overlapping_confirmed,
    }


class RunBody(BaseModel):
    period_start: str
    period_end: str


@router.post("/run")
async def run_payroll(body: RunBody, admin=Depends(get_current_admin)):
    db = get_database()
    label = f"{body.period_start}~{body.period_end}"
    start = date.fromisoformat(body.period_start)
    end = date.fromisoformat(body.period_end)

    employee_ids = {e["_id"] async for e in db.employees.find({"active": True})}
    async for s in db.shifts.find(
        {"business_date": {"$gte": body.period_start, "$lte": body.period_end}, "deleted": {"$ne": True}}
    ):
        employee_ids.add(s["employee_id"])

    for employee_id in employee_ids:
        existing = await db.payrolls.find_one({"employee_id": employee_id, "period_label": label})
        if existing and existing["status"] == "confirmed":
            continue
        inputs = await gather_inputs_for_employee(employee_id, start, end)
        if not inputs["employee"]:
            continue
        overrides = (existing or {}).get("overrides", {})
        result = await compute_employee_payroll(
            employee=inputs["employee"], shifts=inputs["shifts"], pay_rate=inputs["pay_rate"],
            min_wages=inputs["min_wages"], insurance_rate=inputs["insurance_rate"],
            holidays=inputs["holidays"], pay_items=inputs["pay_items"],
            period_start=start, period_end=end, settings=inputs["settings"], overrides=overrides,
        )
        doc = {
            "_id": existing["_id"] if existing else new_id(),
            "period_start": body.period_start, "period_end": body.period_end, "period_label": label,
            "status": "draft", "overrides": overrides, "created_at": now_utc(), **result,
        }
        await db.payrolls.replace_one({"_id": doc["_id"]}, doc, upsert=True)

    await write_audit_log(
        actor=admin["_id"], action="run", target_type="payroll", target_id=label,
        summary=f"정산 실행 ({label})",
    )
    return await get_payrolls(period_start=body.period_start, period_end=body.period_end)


class OverrideBody(BaseModel):
    period_start: str
    period_end: str
    weekly_holiday_excluded: list[str] = []
    insurance_amounts: dict[str, int] = {}


@router.put("/{employee_id}/overrides")
async def update_overrides(employee_id: str, body: OverrideBody, admin=Depends(get_current_admin)):
    db = get_database()
    label = f"{body.period_start}~{body.period_end}"
    existing = await db.payrolls.find_one({"employee_id": employee_id, "period_label": label})
    if not existing or existing["status"] != "draft":
        raise HTTPException(400, "초안 상태의 정산만 수정할 수 있어요.")
    start = date.fromisoformat(body.period_start)
    end = date.fromisoformat(body.period_end)
    overrides = {"weekly_holiday_excluded": body.weekly_holiday_excluded, "insurance_amounts": body.insurance_amounts}
    inputs = await gather_inputs_for_employee(employee_id, start, end)
    result = await compute_employee_payroll(
        employee=inputs["employee"], shifts=inputs["shifts"], pay_rate=inputs["pay_rate"],
        min_wages=inputs["min_wages"], insurance_rate=inputs["insurance_rate"],
        holidays=inputs["holidays"], pay_items=inputs["pay_items"],
        period_start=start, period_end=end, settings=inputs["settings"], overrides=overrides,
    )
    await db.payrolls.update_one({"_id": existing["_id"]}, {"$set": {"overrides": overrides, **result}})
    return doc_out(await db.payrolls.find_one({"_id": existing["_id"]}))


class PeriodBody(BaseModel):
    period_start: str
    period_end: str


@router.post("/confirm")
async def confirm_payroll(body: PeriodBody, admin=Depends(get_current_admin)):
    db = get_database()
    label = f"{body.period_start}~{body.period_end}"
    result = await db.payrolls.update_many(
        {"period_label": label, "status": "draft"},
        {"$set": {"status": "confirmed", "confirmed_at": now_utc(), "confirmed_by": admin["_id"]}},
    )
    await write_audit_log(
        actor=admin["_id"], action="confirm", target_type="payroll", target_id=label,
        summary=f"정산 확정 ({label}, {result.modified_count}명)",
    )
    return await get_payrolls(period_start=body.period_start, period_end=body.period_end)


@router.post("/reopen")
async def reopen_payroll(body: PeriodBody, admin=Depends(get_current_admin)):
    db = get_database()
    label = f"{body.period_start}~{body.period_end}"
    await db.payrolls.update_many(
        {"period_label": label, "status": "confirmed"},
        {"$set": {"status": "draft"}, "$push": {"reopened_history": {"at": now_utc(), "by": admin["_id"]}}},
    )
    await write_audit_log(
        actor=admin["_id"], action="reopen", target_type="payroll", target_id=label,
        summary=f"정산 재오픈 ({label})",
    )
    return await get_payrolls(period_start=body.period_start, period_end=body.period_end)


@router.get("/{period_start}/{period_end}/csv")
async def export_csv(period_start: str, period_end: str):
    db = get_database()
    label = f"{period_start}~{period_end}"
    rows = await db.payrolls.find({"period_label": label}).to_list(length=2000)
    employees = {e["_id"]: e async for e in db.employees.find({})}
    stores = {s["_id"]: s async for s in db.stores.find({})}

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["이름", "구분", "급여관리매장", "기본급", "수당", "보너스공제", "4대보험공제", "실수령액"])
    for r in rows:
        emp = employees.get(r["employee_id"], {})
        store = stores.get(r["pay_store_id"], {})
        allowance = sum(l["amount"] for l in r["lines"] if l["code"] in ("weekly_holiday_pay", "night_premium", "holiday_premium"))
        writer.writerow([
            emp.get("name", "-"),
            "알바" if r["employment_type"] == "part_time" else "직원",
            store.get("name", "-"),
            next((l["amount"] for l in r["lines"] if l["code"].startswith("base_pay")), 0),
            allowance,
            r["gross_pay"] - sum(l["amount"] for l in r["lines"] if l["code"] not in ("weekly_holiday_pay", "night_premium", "holiday_premium") and not l["code"].startswith("base_pay")),
            r["insurance_total"],
            r["net_pay"],
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=payroll_{label}.csv"},
    )
