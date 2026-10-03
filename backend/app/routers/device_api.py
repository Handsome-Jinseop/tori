from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.core.ids import new_id
from app.core.security import hash_token
from app.core.serialize import doc_out, docs_out
from app.core.time import business_date_for, now_utc, parse_iso
from app.db import get_database
from app.routers.admin_settings import get_settings_doc

router = APIRouter(prefix="/api/device", tags=["device"])


async def get_current_device(x_device_key: str | None = Header(default=None)) -> dict:
    if not x_device_key:
        raise HTTPException(401, "기기 인증이 필요해요.")
    db = get_database()
    device = await db.devices.find_one({"api_key_hash": hash_token(x_device_key)})
    if not device or device.get("status") == "inactive":
        raise HTTPException(401, "등록되지 않았거나 비활성화된 기기예요.")
    await db.devices.update_one({"_id": device["_id"]}, {"$set": {"last_seen_at": now_utc()}})
    return device


class RegisterBody(BaseModel):
    code: str
    app_version: str = "1.0.0"


@router.post("/register")
async def register_device(body: RegisterBody):
    db = get_database()
    code_doc = await db.device_codes.find_one({"_id": body.code.upper()})
    if not code_doc or code_doc["used"] or code_doc["expires_at"] < now_utc():
        raise HTTPException(400, "코드가 맞지 않거나 시간이 지났어요.")

    api_key = secrets.token_urlsafe(32)
    device_id = new_id()
    store = await db.stores.find_one({"_id": code_doc["store_id"]})
    await db.devices.insert_one(
        {
            "_id": device_id,
            "store_id": code_doc["store_id"],
            "name": code_doc["device_name"],
            "api_key_hash": hash_token(api_key),
            "status": "active",
            "last_seen_at": now_utc(),
            "app_version": body.app_version,
            "created_at": now_utc(),
        }
    )
    await db.device_codes.update_one({"_id": body.code.upper()}, {"$set": {"used": True}})
    return {"device_id": device_id, "api_key": api_key, "store_name": store["name"]}


@router.get("/config")
async def get_device_config(device: dict = Depends(get_current_device)):
    db = get_database()
    store = await db.stores.find_one({"_id": device["store_id"]})
    settings = await get_settings_doc()
    employees = await db.employees.find(
        {"work_store_ids": device["store_id"], "active": True}
    ).to_list(length=1000)
    enrollments = await db.face_enrollments.find({"device_id": device["_id"]}).to_list(length=1000)
    # 이 기기에서 올라간 신규 직원 요청 중 처리된 것들. 폰은 temp_id 기준으로 멱등하게
    # 반영한다 (이미 실제 employee_id로 바꾼 요청이 다시 와도 temp_id가 로컬에 없으면 무시).
    resolved_requests = await db.employee_requests.find(
        {"device_id": device["_id"], "status": {"$ne": "pending"}}
    ).to_list(length=1000)
    return {
        "server_time": now_utc().isoformat().replace("+00:00", "Z"),
        "store": doc_out(store),
        "face_match_threshold": settings["face_match_threshold"],
        "allow_manual_pick": settings["allow_manual_pick"],
        "allow_pre_approval_clock": settings["allow_pre_approval_clock"],
        "employees": [{"id": e["_id"], "name": e["name"]} for e in employees],
        "enrollments": docs_out(enrollments),
        "resolved_employee_requests": [
            {
                "temp_id": r["temp_id"],
                "status": r["status"],
                "linked_employee_id": r.get("linked_employee_id"),
                "reject_reason": r.get("reject_reason"),
            }
            for r in resolved_requests
        ],
    }


class EnrollBody(BaseModel):
    employee_id: str
    consent_version: str = "v1"
    is_reenroll: bool = False


@router.post("/enrollments")
async def request_enrollment(body: EnrollBody, device: dict = Depends(get_current_device)):
    db = get_database()
    doc = {
        "_id": new_id(),
        "employee_id": body.employee_id,
        "device_id": device["_id"],
        "status": "pending",
        "is_reenroll": body.is_reenroll,
        "requested_at": now_utc(),
        "approved_at": None,
        "approver": None,
        "consent_version": body.consent_version,
        "consent_at": now_utc(),
    }
    await db.face_enrollments.insert_one(doc)
    return doc_out(doc)


class TempEmployeeRequestBody(BaseModel):
    temp_id: str
    name: str


@router.post("/employee-requests")
async def create_employee_request(body: TempEmployeeRequestBody, device: dict = Depends(get_current_device)):
    db = get_database()
    doc = {
        "_id": new_id(),
        "store_id": device["store_id"],
        "device_id": device["_id"],
        "temp_id": body.temp_id,
        "name": body.name,
        "status": "pending",
        "created_at": now_utc(),
        "processed_at": None,
        "processor": None,
        "linked_employee_id": None,
    }
    await db.employee_requests.insert_one(doc)
    await db.face_enrollments.insert_one(
        {
            "_id": new_id(),
            "employee_id": body.temp_id,
            "device_id": device["_id"],
            "status": "pending",
            "is_reenroll": False,
            "requested_at": now_utc(),
            "approved_at": None,
            "approver": None,
            "consent_version": "v1",
            "consent_at": now_utc(),
        }
    )
    return doc_out(doc)


class EventIn(BaseModel):
    uuid: str
    employee_id: str
    kind: str  # in | out
    recorded_at: str
    time_source: str = "device"  # device | manual
    device_clock_at: str | None = None
    input_method: str = "recognized"  # recognized | manual_pick
    similarity_score: float | None = None
    manual_prev_checkout_at: str | None = None


class EventsBody(BaseModel):
    events: list[EventIn]


@router.post("/events")
async def upload_events(body: EventsBody, device: dict = Depends(get_current_device)):
    if len(body.events) > 100:
        raise HTTPException(400, "한 번에 최대 100건까지 업로드할 수 있어요.")
    db = get_database()
    results = []
    for ev in sorted(body.events, key=lambda e: e.device_clock_at or e.recorded_at):
        results.append(await _process_event(db, device, ev))
    return {"results": results}


async def _process_event(db, device: dict, ev: EventIn) -> dict:
    existing = await db.attendance_events.find_one({"_id": ev.uuid})
    if existing:
        return {"uuid": ev.uuid, "status": "duplicate"}

    server_received_at = now_utc()
    recorded_at = parse_iso(ev.recorded_at)
    device_clock_at = parse_iso(ev.device_clock_at) if ev.device_clock_at else recorded_at

    flags: list[str] = []
    if abs((server_received_at - device_clock_at).total_seconds()) > 300:
        flags.append("clock_skew")
    if ev.time_source == "manual":
        flags.append("manual_out" if ev.kind == "in" else "manual_in")
    if ev.input_method == "manual_pick":
        flags.append("manual_pick")

    req = await db.employee_requests.find_one({"temp_id": ev.employee_id, "status": "pending"})
    if req:
        flags.append("temp_employee")

    event_doc = {
        "_id": ev.uuid,
        "employee_id": ev.employee_id,
        "store_id": device["store_id"],
        "device_id": device["_id"],
        "kind": ev.kind,
        "recorded_at": recorded_at,
        "time_source": ev.time_source,
        "device_clock_at": device_clock_at,
        "server_received_at": server_received_at,
        "input_method": ev.input_method,
        "similarity_score": ev.similarity_score,
    }
    await db.attendance_events.insert_one(event_doc)

    business_date = business_date_for(recorded_at)
    open_shift = await db.shifts.find_one(
        {"employee_id": ev.employee_id, "status": "open", "deleted": {"$ne": True}}
    )

    if ev.kind == "in":
        if open_shift:
            if ev.time_source == "manual" and ev.manual_prev_checkout_at:
                prev_checkout = parse_iso(ev.manual_prev_checkout_at)
                await db.shifts.update_one(
                    {"_id": open_shift["_id"]},
                    {"$set": {"check_out": prev_checkout, "status": "closed"},
                     "$addToSet": {"flags": "manual_out"}},
                )
            else:
                flags.append("duplicate_in")
        new_shift = {
            "_id": new_id(),
            "employee_id": ev.employee_id,
            "store_id": device["store_id"],
            "business_date": business_date,
            "check_in": recorded_at,
            "check_out": None,
            "status": "open",
            "flags": flags,
            "memo": "",
            "history": [],
            "deleted": False,
        }
        await db.shifts.insert_one(new_shift)
        shift_id = new_shift["_id"]
    else:
        if open_shift:
            await db.shifts.update_one(
                {"_id": open_shift["_id"]},
                {"$set": {"check_out": recorded_at, "status": "closed"}, "$addToSet": {"flags": {"$each": flags}}},
            )
            shift_id = open_shift["_id"]
        else:
            flags.append("missing_in")
            new_shift = {
                "_id": new_id(),
                "employee_id": ev.employee_id,
                "store_id": device["store_id"],
                "business_date": business_date,
                "check_in": recorded_at if ev.time_source != "manual" else parse_iso(ev.manual_prev_checkout_at or ev.recorded_at),
                "check_out": recorded_at,
                "status": "closed",
                "flags": flags,
                "memo": "",
                "history": [],
                "deleted": False,
            }
            await db.shifts.insert_one(new_shift)
            shift_id = new_shift["_id"]

    return {"uuid": ev.uuid, "status": "accepted", "shift_id": shift_id, "flags": flags}
