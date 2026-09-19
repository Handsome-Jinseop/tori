from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.audit import write_audit_log
from app.core.security import get_current_admin
from app.core.serialize import doc_out
from app.core.time import now_utc
from app.db import get_database

router = APIRouter(
    prefix="/api/admin/enrollments", tags=["admin-enrollments"], dependencies=[Depends(get_current_admin)]
)


async def _enrich(rows: list[dict]) -> list[dict]:
    db = get_database()
    store_ids = {r["device_id"] for r in rows}
    devices = {d["_id"]: d async for d in db.devices.find({"_id": {"$in": list(store_ids)}})}
    store_ids2 = {d["store_id"] for d in devices.values()}
    stores = {s["_id"]: s async for s in db.stores.find({"_id": {"$in": list(store_ids2)}})}
    emp_ids = {r["employee_id"] for r in rows}
    employees = {e["_id"]: e async for e in db.employees.find({"_id": {"$in": list(emp_ids)}})}

    out = []
    for r in rows:
        d = doc_out(r)
        device = devices.get(r["device_id"])
        d["device_name"] = device.get("name") if device else "알 수 없는 기기"
        store = stores.get(device["store_id"]) if device else None
        d["store_name"] = store.get("name") if store else "알 수 없는 매장"
        emp = employees.get(r["employee_id"])
        d["employee_name"] = emp.get("name") if emp else "(임시 등록)"
        out.append(d)
    return out


@router.get("")
async def list_enrollments(status: str = "pending"):
    db = get_database()
    query = {"status": "pending"} if status == "pending" else {"status": {"$in": ["approved", "revoked"]}}
    rows = await db.face_enrollments.find(query).sort("requested_at", -1).to_list(length=1000)
    # 목록에 이름이 없어 신규 직원 요청(A9)으로 처리되는 임시 등록은 이 화면에서 제외.
    emp_ids = {r["employee_id"] for r in rows}
    known_ids = {e["_id"] async for e in db.employees.find({"_id": {"$in": list(emp_ids)}})}
    rows = [r for r in rows if r["employee_id"] in known_ids]
    return await _enrich(rows)


@router.post("/{enrollment_id}/approve")
async def approve_enrollment(enrollment_id: str, admin=Depends(get_current_admin)):
    db = get_database()
    row = await db.face_enrollments.find_one({"_id": enrollment_id})
    if not row:
        raise HTTPException(404, "요청을 찾을 수 없어요.")
    await db.face_enrollments.update_one(
        {"_id": enrollment_id},
        {"$set": {"status": "approved", "approved_at": now_utc(), "approver": admin["_id"]}},
    )
    await write_audit_log(
        actor=admin["_id"], action="approve", target_type="face_enrollment", target_id=enrollment_id,
        summary="얼굴 등록 승인",
    )
    return doc_out(await db.face_enrollments.find_one({"_id": enrollment_id}))


class RejectBody(BaseModel):
    reason: str = ""


@router.post("/{enrollment_id}/reject")
async def reject_enrollment(enrollment_id: str, body: RejectBody, admin=Depends(get_current_admin)):
    db = get_database()
    row = await db.face_enrollments.find_one({"_id": enrollment_id})
    if not row:
        raise HTTPException(404, "요청을 찾을 수 없어요.")
    await db.face_enrollments.delete_one({"_id": enrollment_id})
    await write_audit_log(
        actor=admin["_id"], action="reject", target_type="face_enrollment", target_id=enrollment_id,
        before=doc_out(row), summary=f"얼굴 등록 거절: {body.reason}" if body.reason else "얼굴 등록 거절",
    )
    return {"ok": True}


@router.post("/{enrollment_id}/revoke")
async def revoke_enrollment(enrollment_id: str, admin=Depends(get_current_admin)):
    db = get_database()
    row = await db.face_enrollments.find_one({"_id": enrollment_id})
    if not row:
        raise HTTPException(404, "요청을 찾을 수 없어요.")
    await db.face_enrollments.update_one({"_id": enrollment_id}, {"$set": {"status": "revoked"}})
    await write_audit_log(
        actor=admin["_id"], action="revoke", target_type="face_enrollment", target_id=enrollment_id,
        summary="얼굴 등록 해제 (다음 동기화 때 기기에서 삭제)",
    )
    return doc_out(await db.face_enrollments.find_one({"_id": enrollment_id}))
