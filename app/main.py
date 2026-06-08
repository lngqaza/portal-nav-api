import logging
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pythonjsonlogger import jsonlogger

from app.core.config import settings
from app.core.database import init_db, check_connection, get_hot_path_count, SessionLocal
from app.services.embedding import load_model
from app.services.reranker import load_reranker
from app.routes.query import router as query_router
from app.routes.admin import router as admin_router


def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    )
    logging.root.handlers = [handler]
    logging.root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await init_db()
    load_model()
    load_reranker()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    logging.info("portal-nav-api ready", extra={"version": settings.SERVICE_VERSION})
    yield
    logging.info("portal-nav-api shutting down")


app = FastAPI(
    title="Portal Navigation API",
    description="3-layer navigation assistant: hot-path cache → semantic embeddings → cross-encoder re-rank",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_router, prefix="/query", tags=["query"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])


@app.get("/health", tags=["health"])
async def health():
    from app.services.embedding import _ort_session
    db_ok = await check_connection()
    hot_path_count = await get_hot_path_count()
    return JSONResponse({
        "status": "ok",
        "version": settings.SERVICE_VERSION,
        "db_connected": db_ok,
        "embedding_model_loaded": _ort_session is not None,
        "hot_path_count": hot_path_count,
    })
