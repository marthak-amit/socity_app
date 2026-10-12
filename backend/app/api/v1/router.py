from fastapi import APIRouter

from app.api.v1 import auth, events, health, local_storage, me, orders, passes, societies, uploads
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
if get_settings().storage_backend == "local":
    api_router.include_router(local_storage.router)
