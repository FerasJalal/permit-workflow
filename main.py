import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routers import permits, webhooks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Permit Workflow API",
    description="Automated permit workflow: form → template → sign → distribute",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(permits.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
