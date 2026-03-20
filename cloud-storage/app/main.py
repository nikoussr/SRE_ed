from contextlib import asynccontextmanager

import redis.asyncio as aioredis
import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import create_tables
from app.dependencies import get_current_user, set_redis
from app.middleware.logging import LoggingMiddleware, configure_logging
from app.middleware.metrics import MetricsMiddleware, metrics_endpoint
from app.routes import auth, files, folders, share
from app.services.storage_service import storage_service

configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    logger.info("app.starting", env="production" if not settings.debug else "development")

    await create_tables()

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    set_redis(r)

    storage_service.ensure_bucket()

    logger.info("app.started")
    yield

    # shutdown
    await r.aclose()
    logger.info("app.stopped")


app = FastAPI(
    title="Cloud Storage API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(MetricsMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(files.router)
app.include_router(folders.router)
app.include_router(share.router)

app.add_route("/metrics", metrics_endpoint)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/quota/info")
async def quota_info(current_user=Depends(get_current_user)):
    return {"used_bytes": current_user.used_bytes, "quota_bytes": current_user.quota_bytes}


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("app/static/index.html") as f:
        return f.read()


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    logger.error(
        "error.unhandled",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
