from __future__ import annotations

from typing import Any

from app.core.ids import new_id
from app.core.time import now_utc
from app.db import get_database


async def write_audit_log(
    *,
    actor: str,
    action: str,
    target_type: str,
    target_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    summary: str = "",
) -> None:
    db = get_database()
    await db.audit_logs.insert_one(
        {
            "_id": new_id(),
            "actor": actor,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "before": before,
            "after": after,
            "summary": summary,
            "created_at": now_utc(),
        }
    )
