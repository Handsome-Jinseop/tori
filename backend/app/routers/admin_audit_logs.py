from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_admin
from app.core.serialize import docs_out
from app.db import get_database

router = APIRouter(prefix="/api/admin/audit-logs", tags=["admin-audit-logs"], dependencies=[Depends(get_current_admin)])


@router.get("")
async def list_audit_logs(
    date_from: str = "", date_to: str = "", target_type: str = "", actor: str = "", limit: int = 200
):
    db = get_database()
    query: dict = {}
    if target_type:
        query["target_type"] = target_type
    if actor:
        query["actor"] = actor
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to + "T23:59:59"
        query["created_at"] = rng
    rows = await db.audit_logs.find(query).sort("created_at", -1).to_list(length=limit)
    return docs_out(rows)
