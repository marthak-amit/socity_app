from fastapi import APIRouter

from app.api.v1 import (
    auth,
    events,
    gallery,
    health,
    local_storage,
    me,
    orders,
    passes,
    reports,
    scan,
    societies,
    uploads,
)
from app.core.config import get_settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(societies.router)
api_router.include_router(uploads.router)
api_router.include_router(events.router)
api_router.include_router(orders.router)
api_router.include_router(passes.router)
api_router.include_router(scan.router)
api_router.include_router(reports.router)
api_router.include_router(gallery.router)
if get_settings().storage_backend == "local":
    api_router.include_router(local_storage.router)
