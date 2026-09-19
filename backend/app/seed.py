"""데모 데이터 시드 스크립트. `python -m app.seed`로 실행."""
from __future__ import annotations

import asyncio
import random
from datetime import date, datetime, timedelta

from app.config import get_settings
from app.core.ids import new_id
from app.core.security import hash_token
from app.core.time import KST, UTC
from app.db import ensure_indexes, get_database

random.seed(42)

TODAY = date(2026, 9, 19)

STORE_DEFS = [
    {"name": "토리코코로 별내 본점", "close_time": "22:00", "close_next_day": False, "grace_min": 15},
    {"name": "토리코코로 공릉 직영점", "close_time": "23:00", "close_next_day": False, "grace_min": 15},
    {"name": "직진 닭강정", "close_time": "02:00", "close_next_day": True, "grace_min": 20},
]

ALBA_NAMES = [
    "김서연", "이하은", "박지훈", "최민준", "정수아", "강도윤",
    "윤서준", "임지우", "한소율", "오태양", "신유나", "장민서",
    "권도현", "배시우", "송하윤", "홍예준", "조은우", "문채원",
]
REGULAR_NAMES = ["안현우", "노은지", "차성민", "구예린", "탁민재", "표소연"]

random.shuffle(ALBA_NAMES)
random.shuffle(REGULAR_NAMES)


def kst_dt(d: date, hh: int, mm: int) -> datetime:
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=KST).astimezone(UTC)


async def run_seed() -> None:
    settings = get_settings()
    db = get_database()
    print(f"DB: {settings.mongo_db_name} @ {settings.mongo_url} (mock={settings.use_mock_db})")

    for name in ["stores", "employees", "employee_requests", "assignments", "pay_rates", "min_wages",
                 "insurance_rates", "holidays", "settings", "devices", "device_codes", "face_enrollments",
                 "attendance_events", "shifts", "pay_items", "payrolls", "audit_logs"]:
        await db[name].delete_many({})

    await ensure_indexes()

    # --- settings ---
    await db.settings.insert_one({
        "_id": "global", "night_premium_rate": 0.5, "holiday_premium_rate": 0.5,
        "default_period_start_day": 1, "face_match_threshold": 0.75,
        "allow_manual_pick": True, "allow_pre_approval_clock": True,
    })

    # --- stores ---
    store_ids = []
    for s in STORE_DEFS:
        doc = {"_id": new_id(), **s, "created_at": datetime.now(UTC)}
        await db.stores.insert_one(doc)
        store_ids.append(doc["_id"])

    # --- min wages / insurance rates ---
    await db.min_wages.insert_one({"_id": new_id(), "effective_from": "2025-01-01", "hourly_wage": 9860})
    await db.min_wages.insert_one({"_id": new_id(), "effective_from": "2026-01-01", "hourly_wage": 10320})
    await db.insurance_rates.insert_one({
        "_id": new_id(), "effective_from": "2026-01-01",
        "national_pension": 0.045, "health_insurance": 0.0709,
        "long_term_care": 0.1281, "employment_insurance": 0.009,
    })

    # --- holidays ---
    await db.holidays.insert_one({"_id": new_id(), "date": "2026-09-25", "name": "추석"})
    await db.holidays.insert_one({"_id": new_id(), "date": "2026-09-26", "name": "추석 연휴"})
    await db.holidays.insert_one({"_id": new_id(), "date": "2026-08-15", "name": "광복절"})

    # --- devices ---
    device_ids = []
    for i, store_id in enumerate(store_ids):
        api_key = f"seed-device-key-{i}"
        device_id = new_id()
        last_seen = datetime.now(UTC) - (timedelta(hours=2) if i == 2 else timedelta(minutes=5))
        await db.devices.insert_one({
            "_id": device_id, "store_id": store_id, "name": f"{STORE_DEFS[i]['name'].split()[-1]}-폰1",
            "api_key_hash": hash_token(api_key), "status": "active",
            "last_seen_at": last_seen, "app_version": "1.4.2", "created_at": datetime.now(UTC),
        })
        device_ids.append(device_id)
        print(f"  device api key for {STORE_DEFS[i]['name']}: {api_key}")

    # --- employees ---
    employees = []
    alba_iter = iter(ALBA_NAMES)
    regular_iter = iter(REGULAR_NAMES)
    for si, store_id in enumerate(store_ids):
        for _ in range(6):
            name = next(alba_iter)
            hourly = None if random.random() < 0.5 else random.choice([10320, 10500, 11000, 11500])
            emp = {
                "_id": new_id(), "name": name, "employment_type": "part_time",
                "pay_store_id": store_id, "work_store_ids": [store_id], "active": True,
                "hire_date": (TODAY - timedelta(days=random.randint(60, 400))).isoformat(),
                "face_exempt": random.random() < 0.1, "created_at": datetime.now(UTC),
            }
            await db.employees.insert_one(emp)
            rate = {
                "_id": new_id(), "employee_id": emp["_id"], "effective_from": "2026-01-01",
                "hourly_wage": hourly, "monthly_wage": None,
                "weekly_holiday_pay": random.random() < 0.6,
                "night_premium": random.random() < 0.3,
                "holiday_premium": random.random() < 0.3,
                "insurance_national_pension": random.random() < 0.4,
                "insurance_health": random.random() < 0.4,
                "insurance_employment": random.random() < 0.6,
                "created_at": datetime.now(UTC),
            }
            await db.pay_rates.insert_one(rate)
            employees.append({**emp, "device_id": device_ids[si], "rate": rate})
        for _ in range(2):
            name = next(regular_iter)
            monthly = random.choice([2400000, 2600000, 2800000])
            emp = {
                "_id": new_id(), "name": name, "employment_type": "regular",
                "pay_store_id": store_id, "work_store_ids": [store_id], "active": True,
                "hire_date": (TODAY - timedelta(days=random.randint(200, 900))).isoformat(),
                "face_exempt": False, "created_at": datetime.now(UTC),
            }
            await db.employees.insert_one(emp)
            rate = {
                "_id": new_id(), "employee_id": emp["_id"], "effective_from": "2026-01-01",
                "hourly_wage": None, "monthly_wage": monthly,
                "weekly_holiday_pay": False, "night_premium": False, "holiday_premium": False,
                "insurance_national_pension": True, "insurance_health": True, "insurance_employment": True,
                "created_at": datetime.now(UTC),
            }
            await db.pay_rates.insert_one(rate)
            employees.append({**emp, "device_id": device_ids[si], "rate": rate})

    # --- shifts across Aug 1 ~ today, with occasional anomalies ---
    ANOMALY_RATE = 0.12
    period_start = date(2026, 8, 1)
    day = period_start
    async def add_shift(emp, d: date, store_id: str, start_h, start_m, dur_h, flags=None, open_shift=False):
        check_in = kst_dt(d, start_h, start_m)
        check_out = None if open_shift else check_in + timedelta(hours=dur_h)
        shift_id = new_id()
        doc = {
            "_id": shift_id, "employee_id": emp["_id"], "store_id": store_id,
            "business_date": d.isoformat(), "check_in": check_in, "check_out": check_out,
            "status": "open" if open_shift else "closed",
            "flags": flags or [], "memo": "", "history": [], "reviewed": random.random() < 0.3,
            "deleted": False,
        }
        await db.shifts.insert_one(doc)
        for kind, at in (("in", check_in), ("out", check_out)):
            if at is None:
                continue
            await db.attendance_events.insert_one({
                "_id": new_id(), "employee_id": emp["_id"], "store_id": store_id, "device_id": emp["device_id"],
                "kind": kind, "recorded_at": at, "time_source": "manual" if flags and "manual_in" in flags and kind == "in" else "device",
                "device_clock_at": at, "server_received_at": at, "input_method": "manual_pick" if flags and "manual_pick" in flags else "recognized",
                "similarity_score": None if flags and "manual_pick" in flags else round(random.uniform(0.8, 0.98), 2),
            })
        return doc

    while day <= TODAY:
        weekday = day.weekday()
        for emp in employees:
            if emp["employment_type"] == "regular":
                works_today = weekday < 5
            else:
                works_today = random.random() < 0.55
            if not works_today:
                continue

            is_today = day == TODAY
            open_shift = is_today and random.random() < 0.35
            start_h = random.choice([9, 10, 11, 17, 18])
            start_m = random.choice([0, 15, 30])
            dur = random.choice([4, 5, 6, 7, 8]) if emp["employment_type"] == "part_time" else 9

            flags = []
            roll = random.random()
            if not open_shift and roll < ANOMALY_RATE:
                choice = random.choice(["auto_checkout", "manual_in", "manual_out", "clock_skew", "manual_pick"])
                flags = [choice]

            await add_shift(emp, day, emp["pay_store_id"], start_h, start_m, dur, flags=flags, open_shift=open_shift)
        day += timedelta(days=1)

    # --- pending employee requests (new hires not yet in system) ---
    for i, store_id in enumerate(store_ids[:2]):
        temp_id = f"temp-{new_id()}"
        req_name = "이가을" if i == 0 else "박겨울"
        await db.employee_requests.insert_one({
            "_id": new_id(), "store_id": store_id, "device_id": device_ids[i], "temp_id": temp_id,
            "name": req_name, "status": "pending", "created_at": datetime.now(UTC) - timedelta(days=1),
            "processed_at": None, "processor": None, "linked_employee_id": None,
        })
        await db.face_enrollments.insert_one({
            "_id": new_id(), "employee_id": temp_id, "device_id": device_ids[i], "status": "pending",
            "is_reenroll": False, "requested_at": datetime.now(UTC) - timedelta(days=1),
            "approved_at": None, "approver": None, "consent_version": "v1",
            "consent_at": datetime.now(UTC) - timedelta(days=1),
        })
        for d_off in range(2):
            d = TODAY - timedelta(days=d_off)
            await db.shifts.insert_one({
                "_id": new_id(), "employee_id": temp_id, "store_id": store_id, "business_date": d.isoformat(),
                "check_in": kst_dt(d, 17, 0), "check_out": kst_dt(d, 21, 0), "status": "closed",
                "flags": ["temp_employee"], "memo": "", "history": [], "reviewed": False, "deleted": False,
            })

    # --- extra pending face re-enrollment for an existing employee ---
    reenroll_emp = employees[0]
    await db.face_enrollments.insert_one({
        "_id": new_id(), "employee_id": reenroll_emp["_id"], "device_id": reenroll_emp["device_id"],
        "status": "pending", "is_reenroll": True, "requested_at": datetime.now(UTC) - timedelta(hours=3),
        "approved_at": None, "approver": None, "consent_version": "v1",
        "consent_at": datetime.now(UTC) - timedelta(hours=3),
    })
    approved_emp = employees[1]
    await db.face_enrollments.insert_one({
        "_id": new_id(), "employee_id": approved_emp["_id"], "device_id": approved_emp["device_id"],
        "status": "approved", "is_reenroll": False, "requested_at": datetime.now(UTC) - timedelta(days=30),
        "approved_at": datetime.now(UTC) - timedelta(days=30), "approver": "seed", "consent_version": "v1",
        "consent_at": datetime.now(UTC) - timedelta(days=30),
    })
    for emp in employees[2:6]:
        await db.face_enrollments.insert_one({
            "_id": new_id(), "employee_id": emp["_id"], "device_id": emp["device_id"],
            "status": "approved", "is_reenroll": False, "requested_at": datetime.now(UTC) - timedelta(days=60),
            "approved_at": datetime.now(UTC) - timedelta(days=60), "approver": "seed", "consent_version": "v1",
            "consent_at": datetime.now(UTC) - timedelta(days=60),
        })

    # --- pay items for current period ---
    cur_period_label = "2026-09-01~2026-09-30"
    await db.pay_items.insert_one({
        "_id": new_id(), "employee_id": employees[0]["_id"], "kind": "bonus", "amount": 100000,
        "purpose": "추석 명절 수당", "memo": "", "period_label": cur_period_label,
        "created_by": "seed", "created_at": datetime.now(UTC),
    })
    await db.pay_items.insert_one({
        "_id": new_id(), "employee_id": employees[2]["_id"], "kind": "deduction", "amount": 30000,
        "purpose": "9월 12일 결근 공제", "memo": "", "period_label": cur_period_label,
        "created_by": "seed", "created_at": datetime.now(UTC),
    })

    print(f"Seed complete: {len(store_ids)} stores, {len(employees)} employees.")
    print("Run backend payroll for 2026-08-01~2026-08-31 and confirm it, then 2026-09-01~2026-09-30 as draft,")
    print("via the admin web app (A14 정산) once you've logged in with a passkey.")


if __name__ == "__main__":
    asyncio.run(run_seed())
