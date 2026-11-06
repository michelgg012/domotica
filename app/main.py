import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, zonas
from app.core import db
from app.core.config import settings
from app.ws.handler import router as ws_router

logging.basicConfig(level=settings.log_level,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.open_pool()   # al arrancar
    yield
    await db.close_pool()  # al apagar


app = FastAPI(title="Domótica", lifespan=lifespan)
app.include_router(ws_router)
app.include_router(auth.router)
app.include_router(zonas.router)
# app.include_router(eventos.router)


@app.get("/health")
async def health():
    async with db.get_pool().acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok"}


# desplegar con
# uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
