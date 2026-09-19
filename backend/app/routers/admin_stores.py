from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.audit import write_audit_log
from app.core.ids import new_id
from app.core.security import get_current_admin
from app.core.serialize import doc_out, docs_out
from app.core.time import now_utc
from app.db import get_database

router = APIRouter(prefix="/api/admin/stores", tags=["admin-stores"], dependencies=[Depends(get_current_admin)])


class StoreBody(BaseModel):
    name: str
    close_time: str = "22:00"
    close_next_day: bool = False
    grace_min: int = 15


@router.get("")
async def list_stores():
    db = get_database()
    stores = await db.stores.find({}).sort("name", 1).to_list(length=1000)
    return docs_out(stores)


@router.post("")
async def create_store(body: StoreBody, admin=Depends(get_current_admin)):
    db = get_database()
    doc = {"_id": new_id(), **body.model_dump(), "created_at": now_utc()}
    await db.stores.insert_one(doc)
    await write_audit_log(
        actor=admin["_id"], action="create", target_type="store", target_id=doc["_id"],
        after=body.model_dump(), summary=f"매장 '{body.name}' 추가",
    )
    return doc_out(doc)


@router.put("/{store_id}")
async def update_store(store_id: str, body: StoreBody, admin=Depends(get_current_admin)):
    db = get_database()
    before = await db.stores.find_one({"_id": store_id})
    if not before:
        raise HTTPException(404, "매장을 찾을 수 없어요.")
    await db.stores.update_one({"_id": store_id}, {"$set": body.model_dump()})
    after = await db.stores.find_one({"_id": store_id})
    await write_audit_log(
        actor=admin["_id"], action="update", target_type="store", target_id=store_id,
        before=doc_out(before), after=doc_out(after), summary=f"매장 '{body.name}' 설정 수정",
    )
    return doc_out(after)
