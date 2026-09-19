from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.audit import write_audit_log
from app.core.ids import new_id
from app.core.security import get_current_admin
from app.core.serialize import doc_out, docs_out
from app.db import get_database

router = APIRouter(prefix="/api/admin", tags=["admin-rates"], dependencies=[Depends(get_current_admin)])


class MinWageBody(BaseModel):
    effective_from: str
    hourly_wage: int


@router.get("/min-wages")
async def list_min_wages():
    db = get_database()
    rows = await db.min_wages.find({}).sort("effective_from", -1).to_list(length=1000)
    return docs_out(rows)


@router.post("/min-wages")
async def add_min_wage(body: MinWageBody, admin=Depends(get_current_admin)):
    db = get_database()
    doc = {"_id": new_id(), **body.model_dump()}
    await db.min_wages.insert_one(doc)
    await write_audit_log(
        actor=admin["_id"], action="create", target_type="min_wage", target_id=doc["_id"],
        after=body.model_dump(), summary=f"최저시급 {body.effective_from}부터 {body.hourly_wage}원",
    )
    return doc_out(doc)


async def current_min_wage(as_of: str) -> int:
    db = get_database()
    row = await db.min_wages.find_one({"effective_from": {"$lte": as_of}}, sort=[("effective_from", -1)])
    return row["hourly_wage"] if row else 10030


class InsuranceRateBody(BaseModel):
    effective_from: str
    national_pension: float
    health_insurance: float
    long_term_care: float
    employment_insurance: float


@router.get("/insurance-rates")
async def list_insurance_rates():
    db = get_database()
    rows = await db.insurance_rates.find({}).sort("effective_from", -1).to_list(length=1000)
    return docs_out(rows)


@router.post("/insurance-rates")
async def add_insurance_rate(body: InsuranceRateBody, admin=Depends(get_current_admin)):
    db = get_database()
    doc = {"_id": new_id(), **body.model_dump()}
    await db.insurance_rates.insert_one(doc)
    await write_audit_log(
        actor=admin["_id"], action="create", target_type="insurance_rate", target_id=doc["_id"],
        after=body.model_dump(), summary=f"4대보험 요율 {body.effective_from}부터 갱신",
    )
    return doc_out(doc)


async def current_insurance_rate(as_of: str) -> dict:
    db = get_database()
    row = await db.insurance_rates.find_one({"effective_from": {"$lte": as_of}}, sort=[("effective_from", -1)])
    return row or {
        "national_pension": 0.045,
        "health_insurance": 0.0709,
        "long_term_care": 0.1281,
        "employment_insurance": 0.009,
    }
