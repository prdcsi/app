from fastapi import FastAPI

from app.api.routes import router as api_router
from app.core.database import engine, Base
from app.web.admin import router as admin_router

app = FastAPI(
    title="Meter Photo MVP",
    description="Приём показаний счётчиков ХВС/ГВС по фото",
    version="0.1.0",
)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


app.include_router(api_router)
app.include_router(admin_router)


@app.get("/health")
async def health():
    return {"status": "ok"}