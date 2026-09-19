from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.audit import write_audit_log
from app.core.security import get_current_admin
from app.core.serialize import doc_out
from app.db import get_database

router = APIRouter(prefix="/api/admin/settings", tags=["admin-settings"], dependencies=[Depends(get_current_admin)])

DEFAULTS = {
    "_id": "global",
    "night_premium_rate": 0.5,
    "holiday_premium_rate": 0.5,
    "default_period_start_day": 1,
    "face_match_threshold": 0.75,
    "allow_manual_pick": True,
    "allow_pre_approval_clock": True,
}


async def get_settings_doc() -> dict:
    db = get_database()
    doc = await db.settings.find_one({"_id": "global"})
    if not doc:
        doc = dict(DEFAULTS)
        await db.settings.insert_one(doc)
    return doc


@router.get("")
async def get_settings_api():
    return doc_out(await get_settings_doc())


class SettingsBody(BaseModel):
    night_premium_rate: float | None = None
    holiday_premium_rate: float | None = None
    default_period_start_day: int | None = None
    face_match_threshold: float | None = None
    allow_manual_pick: bool | None = None
    allow_pre_approval_clock: bool | None = None


@router.put("")
async def update_settings(body: SettingsBody, admin=Depends(get_current_admin)):
    db = get_database()
    before = await get_settings_doc()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        await db.settings.update_one({"_id": "global"}, {"$set": updates}, upsert=True)
    after = await get_settings_doc()
    await write_audit_log(
        actor=admin["_id"], action="update", target_type="settings", target_id="global",
        before=doc_out(before), after=doc_out(after), summary="전역 설정 수정",
    )
    return doc_out(after)
