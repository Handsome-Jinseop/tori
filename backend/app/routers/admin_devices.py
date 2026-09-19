from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.audit import write_audit_log
from app.core.ids import new_id
from app.core.security import generate_device_code, get_current_admin
from app.core.serialize import doc_out, docs_out
from app.core.time import as_aware_utc, now_utc
from app.db import get_database

router = APIRouter(prefix="/api/admin/devices", tags=["admin-devices"], dependencies=[Depends(get_current_admin)])

STALE_AFTER_MIN = 30


def _status(device: dict) -> str:
    if device.get("status") == "inactive":
        return "inactive"
    last_seen = device.get("last_seen_at")
    if last_seen and (now_utc() - as_aware_utc(last_seen)) > timedelta(minutes=STALE_AFTER_MIN):
        return "stale"
    if not last_seen:
        return "stale"
    return "ok"


@router.get("")
async def list_devices():
    db = get_database()
    devices = await db.devices.find({}).sort("created_at", 1).to_list(length=1000)
    out = docs_out(devices)
    for d, raw in zip(out, devices):
        d["status"] = _status(raw)
    return out


class IssueCodeBody(BaseModel):
    store_id: str
    device_name: str


@router.post("/codes")
async def issue_code(body: IssueCodeBody, admin=Depends(get_current_admin)):
    db = get_database()
    store = await db.stores.find_one({"_id": body.store_id})
    if not store:
        raise HTTPException(404, "매장을 찾을 수 없어요.")
    code = generate_device_code()
    expires_at = now_utc() + timedelta(minutes=10)
    await db.device_codes.insert_one(
        {
            "_id": code,
            "store_id": body.store_id,
            "device_name": body.device_name,
            "expires_at": expires_at,
            "used": False,
            "created_at": now_utc(),
        }
    )
    await write_audit_log(
        actor=admin["_id"], action="issue_code", target_type="device_code", target_id=code,
        summary=f"{store['name']} 기기 등록 코드 발급",
    )
    return {"code": code, "expires_at": expires_at.isoformat().replace("+00:00", "Z")}


class RenameBody(BaseModel):
    name: str


@router.put("/{device_id}/name")
async def rename_device(device_id: str, body: RenameBody, admin=Depends(get_current_admin)):
    db = get_database()
    device = await db.devices.find_one({"_id": device_id})
    if not device:
        raise HTTPException(404, "기기를 찾을 수 없어요.")
    await db.devices.update_one({"_id": device_id}, {"$set": {"name": body.name}})
    await write_audit_log(
        actor=admin["_id"], action="update", target_type="device", target_id=device_id,
        before={"name": device.get("name")}, after={"name": body.name}, summary="기기 이름 수정",
    )
    return doc_out(await db.devices.find_one({"_id": device_id}))


@router.post("/{device_id}/deactivate")
async def deactivate_device(device_id: str, admin=Depends(get_current_admin)):
    db = get_database()
    device = await db.devices.find_one({"_id": device_id})
    if not device:
        raise HTTPException(404, "기기를 찾을 수 없어요.")
    await db.devices.update_one({"_id": device_id}, {"$set": {"status": "inactive"}})
    await write_audit_log(
        actor=admin["_id"], action="deactivate", target_type="device", target_id=device_id,
        summary=f"기기 '{device.get('name')}' 비활성화",
    )
    return doc_out(await db.devices.find_one({"_id": device_id}))
