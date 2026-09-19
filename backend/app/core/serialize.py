from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any


def doc_out(doc: dict | None) -> dict | None:
    """Mongo 문서를 API 응답용으로 변환: _id -> id, datetime/date -> ISO 문자열."""
    if doc is None:
        return None
    out: dict[str, Any] = {}
    for k, v in doc.items():
        key = "id" if k == "_id" else k
        out[key] = _convert(v)
    return out


def _convert(v: Any) -> Any:
    if isinstance(v, datetime):
        # Mongo round-trips datetimes as naive UTC; treat naive values as UTC explicitly
        # so the serialized string always carries an explicit offset for the frontend.
        aware = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _convert(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_convert(x) for x in v]
    return v


def docs_out(docs: list[dict]) -> list[dict]:
    return [doc_out(d) for d in docs]
