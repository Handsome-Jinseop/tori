from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.security import get_current_admin
from app.db import get_database

router = APIRouter(prefix="/api/admin/reports", tags=["admin-reports"], dependencies=[Depends(get_current_admin)])


@router.get("/hours")
async def hours_summary(
    period_start: str = Query(...), period_end: str = Query(...), employment_type: str = ""
):
    db = get_database()
    stores = await db.stores.find({}).sort("name", 1).to_list(length=100)
    emp_query: dict = {}
    if employment_type:
        emp_query["employment_type"] = employment_type
    employees = await db.employees.find(emp_query).sort("name", 1).to_list(length=2000)
    store_map = {s["_id"]: s["name"] for s in stores}

    rows = []
    store_totals = {s["_id"]: 0 for s in stores}
    grand_total = 0
    for e in employees:
        shifts = await db.shifts.find({
            "employee_id": e["_id"],
            "business_date": {"$gte": period_start, "$lte": period_end},
            "deleted": {"$ne": True},
        }).to_list(length=2000)
        cells: dict[str, int] = {}
        for s in shifts:
            if not s.get("check_out"):
                continue
            minutes = round((s["check_out"] - s["check_in"]).total_seconds() / 60)
            cells[s["store_id"]] = cells.get(s["store_id"], 0) + minutes
            store_totals[s["store_id"]] = store_totals.get(s["store_id"], 0) + minutes
        total = sum(cells.values())
        if total == 0:
            continue
        grand_total += total
        rows.append({
            "employee_id": e["_id"], "name": e["name"], "employment_type": e["employment_type"],
            "pay_store_id": e["pay_store_id"], "pay_store_name": store_map.get(e["pay_store_id"], "-"),
            "cells": cells, "total_minutes": total,
        })

    return {
        "stores": [{"id": s["_id"], "name": s["name"]} for s in stores],
        "rows": rows,
        "store_totals": store_totals,
        "grand_total": grand_total,
    }


@router.get("/stores")
async def store_report(period_start: str = Query(...), period_end: str = Query(...)):
    db = get_database()
    stores = await db.stores.find({}).sort("name", 1).to_list(length=100)
    label = f"{period_start}~{period_end}"
    payrolls = await db.payrolls.find({"period_label": label}).to_list(length=2000)
    employees = {e["_id"]: e async for e in db.employees.find({})}

    store_rows = []
    for s in stores:
        pts = [p for p in payrolls if p["pay_store_id"] == s["_id"]]
        part_time_cost = sum(p["gross_pay"] for p in pts if p["employment_type"] == "part_time")
        regular_cost = sum(p["gross_pay"] for p in pts if p["employment_type"] == "regular")
        deduction_total = sum(p["deduction_total"] + p["insurance_total"] for p in pts)
        net_total = sum(p["net_pay"] for p in pts)
        total_hours = round(sum(sum(p["hours_by_store"].values()) for p in pts) / 60, 1)
        store_rows.append({
            "store_id": s["_id"], "name": s["name"],
            "part_time_cost": part_time_cost, "regular_cost": regular_cost,
            "total_cost": part_time_cost + regular_cost,
            "deduction_total": deduction_total, "net_total": net_total, "total_hours": total_hours,
        })

    ranking = sorted(
        [
            {
                "employee_id": p["employee_id"], "name": employees.get(p["employee_id"], {}).get("name", "-"),
                "employment_type": p["employment_type"], "pay_store_id": p["pay_store_id"], "net_pay": p["net_pay"],
            }
            for p in payrolls
        ],
        key=lambda r: -r["net_pay"],
    )
    is_draft = any(p["status"] == "draft" for p in payrolls)
    return {"period_label": label, "is_draft": is_draft, "stores": store_rows, "ranking": ranking}


@router.get("/stores/{period_start}/{period_end}/csv")
async def store_report_csv(period_start: str, period_end: str):
    data = await store_report(period_start=period_start, period_end=period_end)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["매장", "알바 인건비", "직원 인건비", "인건비 합계", "공제 합계", "실수령 합계", "근무시간 합계"])
    for row in data["stores"]:
        writer.writerow([
            row["name"], row["part_time_cost"], row["regular_cost"], row["total_cost"],
            row["deduction_total"], row["net_total"], row["total_hours"],
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=store_report_{period_start}_{period_end}.csv"},
    )
