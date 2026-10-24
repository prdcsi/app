import time
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.core.database import engine, Base
from app.core.logging_config import get_logger, new_request_id, setup_logging
from app.web.admin import router as admin_router

setup_logging()
logger = get_logger(__name__)

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

app = FastAPI(
    title="Meter Photo MVP",
    description="Приём показаний счётчиков ХВС/ГВС по фото",
    version="0.1.0",
)


@app.on_event("startup")
async def startup():
    logger.info("application_started")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.on_event("shutdown")
async def shutdown():
    logger.info("application_stopped")


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = new_request_id()
    request_id_ctx.set(request_id)

    start_time = time.perf_counter()

    logger.info(
        "http_request_started",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else None,
        },
    )

    try:
        response = await call_next(request)
    except Exception:
        process_time = time.perf_counter() - start_time

        logger.exception(
            "http_request_failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "process_time": round(process_time, 3),
            },
        )

        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    process_time = time.perf_counter() - start_time

    logger.info(
        "http_request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time": round(process_time, 3),
            "client_ip": request.client.host if request.client else None,
        },
    )

    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(api_router)
app.include_router(admin_router)


@app.get("/health")
async def health():
    return {"status": "ok"}