from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.audit import write_audit_log
from app.core.ids import new_id
from app.core.security import get_current_admin
from app.core.serialize import doc_out, docs_out
from app.core.time import now_utc
from app.db import get_database

router = APIRouter(prefix="/api/admin/pay-items", tags=["admin-pay-items"], dependencies=[Depends(get_current_admin)])


async def _is_confirmed(employee_id: str, period_label: str) -> bool:
    db = get_database()
    p = await db.payrolls.find_one({"employee_id": employee_id, "period_label": period_label, "status": "confirmed"})
    return p is not None


async def _enrich(rows: list[dict]) -> list[dict]:
    db = get_database()
    emp_ids = {r["employee_id"] for r in rows}
    employees = {e["_id"]: e async for e in db.employees.find({"_id": {"$in": list(emp_ids)}})}
    out = []
    for r in rows:
        d = doc_out(r)
        emp = employees.get(r["employee_id"])
        d["employee_name"] = emp["name"] if emp else "-"
        d["employment_type"] = emp.get("employment_type") if emp else None
        d["pay_store_id"] = emp.get("pay_store_id") if emp else None
        out.append(d)
    return out


@router.get("")
async def list_pay_items(period_label: str = "", employee_id: str = "", kind: str = ""):
    db = get_database()
    query: dict = {}
    if period_label:
        query["period_label"] = period_label
    if employee_id:
        query["employee_id"] = employee_id
    if kind:
        query["kind"] = kind
    rows = await db.pay_items.find(query).sort("created_at", -1).to_list(length=1000)
    enriched = await _enrich(rows)
    bonus_total = sum(r["amount"] for r in enriched if r["kind"] == "bonus")
    deduction_total = sum(r["amount"] for r in enriched if r["kind"] == "deduction")
    return {"items": enriched, "bonus_total": bonus_total, "deduction_total": deduction_total}


class PayItemBody(BaseModel):
    employee_id: str
    kind: str  # bonus | deduction
    amount: int
    purpose: str
    memo: str = ""
    period_label: str


@router.post("")
async def create_pay_item(body: PayItemBody, admin=Depends(get_current_admin)):
    if await _is_confirmed(body.employee_id, body.period_label):
        raise HTTPException(409, "이 정산은 확정됐어요. 수정하려면 정산을 재오픈해야 해요.")
    db = get_database()
    doc = {"_id": new_id(), **body.model_dump(), "created_by": admin["_id"], "created_at": now_utc()}
    await db.pay_items.insert_one(doc)
    await write_audit_log(
        actor=admin["_id"], action="create", target_type="pay_item", target_id=doc["_id"],
        after=body.model_dump(), summary=f"{'보너스' if body.kind=='bonus' else '공제'} 등록: {body.purpose}",
    )
    return (await _enrich([doc]))[0]


@router.put("/{item_id}")
async def update_pay_item(item_id: str, body: PayItemBody, admin=Depends(get_current_admin)):
    db = get_database()
    before = await db.pay_items.find_one({"_id": item_id})
    if not before:
        raise HTTPException(404, "항목을 찾을 수 없어요.")
    if await _is_confirmed(before["employee_id"], before["period_label"]):
        raise HTTPException(409, "이 정산은 확정됐어요. 수정하려면 정산을 재오픈해야 해요.")
    await db.pay_items.update_one({"_id": item_id}, {"$set": body.model_dump()})
    after = await db.pay_items.find_one({"_id": item_id})
    await write_audit_log(
        actor=admin["_id"], action="update", target_type="pay_item", target_id=item_id,
        before=doc_out(before), after=doc_out(after), summary=f"항목 수정: {body.purpose}",
    )
    return (await _enrich([after]))[0]


@router.delete("/{item_id}")
async def delete_pay_item(item_id: str, admin=Depends(get_current_admin)):
    db = get_database()
    before = await db.pay_items.find_one({"_id": item_id})
    if not before:
        raise HTTPException(404, "항목을 찾을 수 없어요.")
    if await _is_confirmed(before["employee_id"], before["period_label"]):
        raise HTTPException(409, "이 정산은 확정됐어요. 수정하려면 정산을 재오픈해야 해요.")
    await db.pay_items.delete_one({"_id": item_id})
    await write_audit_log(
        actor=admin["_id"], action="delete", target_type="pay_item", target_id=item_id,
        before=doc_out(before), summary=f"항목 삭제: {before['purpose']}",
    )
    return {"ok": True}
