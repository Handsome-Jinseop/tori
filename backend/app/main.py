from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import ensure_indexes, get_database
from app.routers import (
    admin_audit_logs,
    admin_auth,
    admin_dashboard,
    admin_devices,
    admin_employee_requests,
    admin_employees,
    admin_enrollments,
    admin_holidays,
    admin_pay_items,
    admin_payrolls,
    admin_rates,
    admin_reports,
    admin_settings,
    admin_shifts,
    admin_stores,
    device_api,
)
from app.services.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    settings = get_settings()
    if settings.use_mock_db:
        db = get_database()
        if await db.stores.count_documents({}) == 0:
            from app.seed import run_seed

            await run_seed()
    scheduler = start_scheduler()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="출퇴근·급여 관리 시스템 API", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    admin_auth.router,
    admin_dashboard.router,
    admin_stores.router,
    admin_employees.router,
    admin_employee_requests.router,
    admin_rates.router,
    admin_holidays.router,
    admin_devices.router,
    admin_enrollments.router,
    admin_shifts.router,
    admin_pay_items.router,
    admin_payrolls.router,
    admin_reports.router,
    admin_settings.router,
    admin_audit_logs.router,
    device_api.router,
):
    app.include_router(router)


@app.get("/api/health")
async def health():
    return {"ok": True}
