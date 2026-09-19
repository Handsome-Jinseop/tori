from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from app.core.time import KST, to_kst
from app.db import get_database

RULE_VERSION = "2026.09.19"


async def _min_wage_as_of(min_wages: list[dict], as_of: str) -> int:
    candidates = [m for m in min_wages if m["effective_from"] <= as_of]
    if not candidates:
        return 10030
    return max(candidates, key=lambda m: m["effective_from"])["hourly_wage"]


def _night_minutes(check_in: datetime, check_out: datetime) -> float:
    """22:00~익일06:00(KST)와 겹치는 분."""
    start = to_kst(check_in)
    end = to_kst(check_out)
    total = 0.0
    cursor = start
    while cursor < end:
        day_start = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
        night_start = day_start + timedelta(hours=22)
        night_end = day_start + timedelta(days=1, hours=6)
        seg_end = min(end, day_start + timedelta(days=1))
        ov_start = max(cursor, night_start)
        ov_end = min(seg_end, night_end)
        if ov_end > ov_start:
            total += (ov_end - ov_start).total_seconds() / 60
        cursor = seg_end
    return total


async def compute_employee_payroll(
    *,
    employee: dict,
    shifts: list[dict],
    pay_rate: dict | None,
    min_wages: list[dict],
    insurance_rate: dict,
    holidays: set[str],
    pay_items: list[dict],
    period_start: date,
    period_end: date,
    settings: dict,
    overrides: dict[str, Any] | None = None,
) -> dict:
    overrides = overrides or {}
    is_part_time = employee["employment_type"] == "part_time"
    lines: list[dict] = []
    hours_by_store: dict[str, float] = {}

    for s in shifts:
        if not s.get("check_out"):
            continue
        minutes = (s["check_out"] - s["check_in"]).total_seconds() / 60
        hours_by_store[s["store_id"]] = hours_by_store.get(s["store_id"], 0) + minutes

    if is_part_time:
        base_amount = 0.0
        for s in shifts:
            if not s.get("check_out"):
                continue
            minutes = (s["check_out"] - s["check_in"]).total_seconds() / 60
            wage = (pay_rate or {}).get("hourly_wage") or await _min_wage_as_of(min_wages, s["business_date"])
            base_amount += minutes / 60 * wage
        base_amount = round(base_amount)
        total_hours = sum(hours_by_store.values())
        lines.append({"code": "base_pay", "name": "기본급", "amount": base_amount,
                       "basis": f"{round(total_hours / 60, 1)}시간"})

        if pay_rate and pay_rate.get("weekly_holiday_pay"):
            weeks: dict[str, float] = {}
            for s in shifts:
                if not s.get("check_out"):
                    continue
                d = date.fromisoformat(s["business_date"])
                monday = d - timedelta(days=d.weekday())
                sunday = monday + timedelta(days=6)
                if not (period_start <= sunday <= period_end):
                    continue
                week_label = monday.isoformat()
                minutes = (s["check_out"] - s["check_in"]).total_seconds() / 60
                weeks[week_label] = weeks.get(week_label, 0) + minutes
            weekly_holiday_total = 0
            weekly_detail = []
            excluded = overrides.get("weekly_holiday_excluded", [])
            for week_label, minutes in sorted(weeks.items()):
                hours = minutes / 60
                eligible = hours >= 15 and week_label not in excluded
                wage = (pay_rate or {}).get("hourly_wage") or await _min_wage_as_of(min_wages, week_label)
                amount = round(min(hours, 40) / 5 * wage) if eligible else 0
                weekly_detail.append({
                    "week": week_label, "hours": round(hours, 1), "eligible": eligible, "amount": amount,
                })
                weekly_holiday_total += amount
            lines.append({"code": "weekly_holiday_pay", "name": "주휴수당", "amount": weekly_holiday_total,
                           "basis": weekly_detail})

        if pay_rate and pay_rate.get("night_premium"):
            night_minutes_total = 0.0
            night_amount = 0.0
            rate = settings.get("night_premium_rate", 0.5)
            for s in shifts:
                if not s.get("check_out"):
                    continue
                nm = _night_minutes(s["check_in"], s["check_out"])
                wage = (pay_rate or {}).get("hourly_wage") or await _min_wage_as_of(min_wages, s["business_date"])
                night_minutes_total += nm
                night_amount += nm / 60 * wage * rate
            lines.append({"code": "night_premium", "name": "야간 가산", "amount": round(night_amount),
                           "basis": f"{round(night_minutes_total / 60, 1)}시간 × {int(rate * 100)}%"})

        if pay_rate and pay_rate.get("holiday_premium"):
            holiday_minutes_total = 0.0
            holiday_amount = 0.0
            rate = settings.get("holiday_premium_rate", 0.5)
            for s in shifts:
                if not s.get("check_out") or s["business_date"] not in holidays:
                    continue
                minutes = (s["check_out"] - s["check_in"]).total_seconds() / 60
                wage = (pay_rate or {}).get("hourly_wage") or await _min_wage_as_of(min_wages, s["business_date"])
                holiday_minutes_total += minutes
                holiday_amount += minutes / 60 * wage * rate
            lines.append({"code": "holiday_premium", "name": "휴일 가산", "amount": round(holiday_amount),
                           "basis": f"{round(holiday_minutes_total / 60, 1)}시간 × {int(rate * 100)}%"})
    else:
        monthly = (pay_rate or {}).get("monthly_wage") or 0
        days_in_period = (period_end - period_start).days + 1
        hire_date = date.fromisoformat(employee["hire_date"]) if employee.get("hire_date") else None
        resigned_at = employee.get("resigned_at")
        resign_date = to_kst(resigned_at).date() if resigned_at else None
        work_start = max(period_start, hire_date) if hire_date and hire_date > period_start else period_start
        work_end = min(period_end, resign_date) if resign_date and resign_date < period_end else period_end
        worked_days = max(0, (work_end - work_start).days + 1)
        if worked_days < days_in_period:
            amount = round(monthly * worked_days / days_in_period)
            basis = f"일할 계산 {worked_days}/{days_in_period}일"
        else:
            amount = monthly
            basis = "월급(포괄임금)"
        lines.append({"code": "base_pay", "name": "기본급(월급)", "amount": amount, "basis": basis})

    bonus_total = 0
    deduction_total_items = 0
    item_lines = []
    for item in pay_items:
        if item["kind"] == "bonus":
            bonus_total += item["amount"]
        else:
            deduction_total_items += item["amount"]
        item_lines.append({
            "code": f"item:{item['_id']}", "name": item["purpose"], "amount": item["amount"],
            "kind": item["kind"], "basis": item.get("memo", ""),
        })
    if item_lines:
        lines.append({"code": "pay_items", "name": "보너스·공제", "amount": bonus_total - deduction_total_items,
                       "basis": item_lines})

    gross = sum(l["amount"] for l in lines if l["code"] != "pay_items") + bonus_total

    insurance_lines = []
    insurance_total = 0
    insurance_base = gross - deduction_total_items
    insurance_fields = {
        "insurance_national_pension": ("national_pension", "국민연금"),
        "insurance_health": ("health_insurance", "건강보험"),
        "insurance_employment": ("employment_insurance", "고용보험"),
    }
    for field, (rate_key, label) in insurance_fields.items():
        if pay_rate and pay_rate.get(field):
            rate = insurance_rate.get(rate_key, 0)
            amount = int(insurance_base * rate)
            insurance_lines.append({"code": rate_key, "name": label, "amount": amount, "rate": rate})
            insurance_total += amount
            if field == "insurance_health":
                lt_rate = insurance_rate.get("long_term_care", 0)
                lt_amount = int(amount * lt_rate)
                insurance_lines.append({"code": "long_term_care", "name": "장기요양", "amount": lt_amount, "rate": lt_rate})
                insurance_total += lt_amount

    for k, v in overrides.get("insurance_amounts", {}).items():
        for line in insurance_lines:
            if line["code"] == k:
                insurance_total += v - line["amount"]
                line["amount"] = v

    net_pay = gross - deduction_total_items - insurance_total

    return {
        "employee_id": employee["_id"],
        "pay_store_id": employee["pay_store_id"],
        "employment_type": employee["employment_type"],
        "hours_by_store": {k: round(v) for k, v in hours_by_store.items()},
        "lines": lines,
        "gross_pay": round(gross),
        "deduction_total": round(deduction_total_items),
        "insurance_lines": insurance_lines,
        "insurance_total": insurance_total,
        "net_pay": round(net_pay),
        "rule_version": RULE_VERSION,
    }


async def gather_inputs_for_employee(employee_id: str, period_start: date, period_end: date) -> dict:
    db = get_database()
    employee = await db.employees.find_one({"_id": employee_id})
    pay_rate = await db.pay_rates.find_one(
        {"employee_id": employee_id, "effective_from": {"$lte": period_start.isoformat()}},
        sort=[("effective_from", -1)],
    )
    min_wages = await db.min_wages.find({}).to_list(length=1000)
    insurance_rate = await db.insurance_rates.find_one(
        {"effective_from": {"$lte": period_start.isoformat()}}, sort=[("effective_from", -1)]
    ) or {"national_pension": 0.045, "health_insurance": 0.0709, "long_term_care": 0.1281, "employment_insurance": 0.009}
    holidays = {h["date"] async for h in db.holidays.find(
        {"date": {"$gte": period_start.isoformat(), "$lte": period_end.isoformat()}}
    )}
    shifts = await db.shifts.find({
        "employee_id": employee_id,
        "business_date": {"$gte": period_start.isoformat(), "$lte": period_end.isoformat()},
        "deleted": {"$ne": True},
    }).to_list(length=5000)
    period_label = f"{period_start.isoformat()}~{period_end.isoformat()}"
    pay_items = await db.pay_items.find(
        {"employee_id": employee_id, "period_label": period_label}
    ).to_list(length=200)
    settings = await db.settings.find_one({"_id": "global"}) or {}
    return {
        "employee": employee, "pay_rate": pay_rate, "min_wages": min_wages,
        "insurance_rate": insurance_rate, "holidays": holidays, "shifts": shifts,
        "pay_items": pay_items, "settings": settings,
    }
