from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_database() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is not None:
        return _db

    settings = get_settings()
    if settings.use_mock_db:
        from mongomock_motor import AsyncMongoMockClient

        _client = AsyncMongoMockClient()
    else:
        _client = AsyncIOMotorClient(settings.mongo_url)
    _db = _client[settings.mongo_db_name]
    return _db


COLLECTIONS = [
    "stores",
    "employees",
    "employee_requests",
    "assignments",
    "pay_rates",
    "min_wages",
    "insurance_rates",
    "holidays",
    "settings",
    "devices",
    "face_enrollments",
    "attendance_events",
    "shifts",
    "pay_items",
    "payrolls",
    "admin_users",
    "audit_logs",
    "login_requests",
]


async def ensure_indexes() -> None:
    db = get_database()
    await db.shifts.create_index([("employee_id", 1), ("business_date", 1)])
    await db.shifts.create_index([("store_id", 1), ("business_date", 1)])
    await db.shifts.create_index([("status", 1)])
    await db.payrolls.create_index([("period_label", 1), ("employee_id", 1)], unique=True)
    await db.pay_rates.create_index([("employee_id", 1), ("effective_from", 1)])
    await db.assignments.create_index([("employee_id", 1), ("effective_from", 1)])
    await db.pay_items.create_index([("employee_id", 1), ("period_label", 1)])
    await db.holidays.create_index([("date", 1)], unique=True)
    await db.face_enrollments.create_index([("device_id", 1), ("status", 1)])
    await db.devices.create_index([("api_key_hash", 1)])
