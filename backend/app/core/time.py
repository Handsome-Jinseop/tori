from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
UTC = timezone.utc


def now_utc() -> datetime:
    return datetime.now(UTC)


def as_aware_utc(dt: datetime) -> datetime:
    """Mongo round-trips datetimes as naive UTC; make them tz-aware for arithmetic."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def to_kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(KST)


def business_date_for(check_in_utc: datetime) -> str:
    """근무일은 출근 시각(KST) 기준의 날짜."""
    kst = to_kst(check_in_utc)
    return kst.date().isoformat()


def period_bounds(reference: date, start_day: int) -> tuple[date, date]:
    """start_day(예: 1 또는 16)를 기준으로 reference가 속한 정산 기간의 (시작일, 종료일)을 반환."""
    start_day = max(1, min(start_day, 28))

    def month_add(y: int, m: int, delta: int) -> tuple[int, int]:
        idx = (y * 12 + (m - 1)) + delta
        return idx // 12, idx % 12 + 1

    if reference.day >= start_day:
        sy, sm = reference.year, reference.month
    else:
        sy, sm = month_add(reference.year, reference.month, -1)
    start = date(sy, sm, start_day)

    ey, em = month_add(sy, sm, 1)
    last_day_next = calendar.monthrange(ey, em)[1]
    end_day = min(start_day - 1, last_day_next) if start_day > 1 else last_day_next
    if start_day == 1:
        end = date(ey, em, last_day_next)
    else:
        end = date(ey, em, end_day)
    return start, end


def period_label(start: date, end: date) -> str:
    return f"{start.isoformat()}~{end.isoformat()}"


def next_period_start(start_day: int, after: date | None = None) -> date:
    ref = after or date.today()
    _, end = period_bounds(ref, start_day)
    return end + timedelta(days=1)


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def week_bounds_kst(d: date) -> tuple[date, date]:
    """월요일 시작 주의 (시작일, 종료일=일요일)."""
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday
