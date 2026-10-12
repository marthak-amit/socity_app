import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = []
    if settings.background_jobs:
        from app.services.jobs import start_background_jobs

        tasks = start_background_jobs()
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(
    title="SocietyPass API",
    version="0.1.0",
    description=(
        "Multi-tenant API for housing societies to run events and sell passes.\n\n"
        "**Auth**: `POST /api/v1/auth/otp/request` → `POST /api/v1/auth/otp/verify` → use `access_token` as "
        "`Authorization: Bearer ...`. Every society-scoped route lives under `/api/v1/societies/{society_id}` "
        "and enforces membership + role server-side."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = [{"loc": [str(x) for x in e["loc"]], "msg": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": {"code": "validation_error", "message": "Invalid input", "errors": errors}})


app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root():
    return {"name": "SocietyPass API", "docs": "/docs"}
