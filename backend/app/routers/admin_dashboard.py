from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends

from app.core.security import get_current_admin
from app.core.serialize import doc_out
from app.core.time import as_aware_utc, now_utc, period_bounds
from app.db import get_database
from app.routers.admin_devices import STALE_AFTER_MIN, _status
from app.routers.admin_employee_requests import _enrich as enrich_requests
from app.routers.admin_enrollments import _enrich as enrich_enrollments
from app.routers.admin_settings import get_settings_doc

router = APIRouter(prefix="/api/admin/dashboard", tags=["admin-dashboard"], dependencies=[Depends(get_current_admin)])

FLAG_LABELS = {
    "clock_skew": "시각 이상", "duplicate_in": "출근 중복", "missing_in": "출근 누락",
    "auto_checkout": "자동 퇴근", "manual_out": "퇴근 수기 입력", "manual_in": "출근 수기 입력",
    "manual_pick": "수기 선택", "temp_employee": "임시 직원", "manual_edit": "관리자 수정",
    "manual_add": "관리자 추가",
}


@router.get("")
async def dashboard(store_id: str = ""):
    db = get_database()
    settings = await get_settings_doc()
    start, end = period_bounds(date.today(), settings["default_period_start_day"])

    device_query = {} if not store_id else {"store_id": store_id}
    devices = await db.devices.find(device_query).to_list(length=100)
    stores = await db.stores.find({} if not store_id else {"_id": store_id}).sort("name", 1).to_list(length=100)
    store_map = {s["_id"]: s for s in stores}

    device_warnings = []
    for d in devices:
        if _status(d) == "stale" and d.get("status") != "inactive":
            store = store_map.get(d["store_id"])
            minutes = None
            if d.get("last_seen_at"):
                minutes = int((now_utc() - as_aware_utc(d["last_seen_at"])).total_seconds() / 60)
            device_warnings.append({
                "device_id": d["_id"], "device_name": d["name"],
                "store_name": store["name"] if store else "-", "store_id": d["store_id"],
                "minutes_since_sync": minutes,
            })

    requests = await db.employee_requests.find({"status": "pending"}).to_list(length=200)
    if store_id:
        requests = [r for r in requests if r["store_id"] == store_id]
    employee_requests = await enrich_requests(requests)

    enrollments = await db.face_enrollments.find({"status": "pending"}).to_list(length=200)
    enrollments_enriched = await enrich_enrollments(enrollments)
    if store_id:
        enrollments_enriched = [e for e in enrollments_enriched if e.get("store_name") == store_map.get(store_id, {}).get("name")]

    review_query = {
        "business_date": {"$gte": start.isoformat(), "$lte": end.isoformat()},
        "flags.0": {"$exists": True}, "reviewed": {"$ne": True}, "deleted": {"$ne": True},
    }
    if store_id:
        review_query["store_id"] = store_id
    needs_review = await db.shifts.find(review_query).to_list(length=5000)
    by_flag: dict[str, int] = {}
    for s in needs_review:
        for f in s.get("flags", []):
            by_flag[f] = by_flag.get(f, 0) + 1

    store_cards = []
    for s in stores:
        open_shifts = await db.shifts.find(
            {"store_id": s["_id"], "status": "open", "deleted": {"$ne": True}}
        ).to_list(length=200)
        employees = {e["_id"]: e async for e in db.employees.find({"_id": {"$in": [x["employee_id"] for x in open_shifts]}})}
        working = [
            {"employee_id": os["employee_id"], "name": employees.get(os["employee_id"], {}).get("name", "-"),
             "check_in": doc_out(os)["check_in"]}
            for os in open_shifts
        ]
        store_devices = [d for d in devices if d["store_id"] == s["_id"]]
        last_sync = max((d.get("last_seen_at") for d in store_devices if d.get("last_seen_at")), default=None)
        device_status = _status(store_devices[0]) if store_devices else "none"
        store_cards.append({
            "store_id": s["_id"], "name": s["name"], "working": working, "working_count": len(working),
            "last_sync": last_sync.isoformat().replace("+00:00", "Z") if last_sync else None,
            "device_status": device_status,
        })

    return {
        "date": date.today().isoformat(),
        "device_warnings": device_warnings,
        "employee_requests": employee_requests,
        "enrollments_pending": enrollments_enriched,
        "needs_review_count": len(needs_review),
        "needs_review_by_flag": [{"flag": k, "label": FLAG_LABELS.get(k, k), "count": v} for k, v in by_flag.items()],
        "stores": store_cards,
        "period_start": start.isoformat(), "period_end": end.isoformat(),
    }
