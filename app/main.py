import asyncio
import structlog
from fastapi import FastAPI
from contextlib import asynccontextmanager
from prometheus_client import start_http_server

from app.core.config import settings
from app.core.logging_utils import setup_logging
from app.core.engine import ltx_engine
from app.grpc_server import serve_grpc

setup_logging()
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}", event_id="SERVICE_START")

    try:
        start_http_server(settings.METRICS_PORT)
        logger.info(f"Metrics Server exposed on port {settings.METRICS_PORT}", event_id="METRICS_SERVER_READY")
    except Exception as e:
        pass

    ltx_engine.initialize()
    grpc_task = asyncio.create_task(serve_grpc())

    yield

    logger.info("Shutting down...", event_id="SERVICE_SHUTDOWN")
    grpc_task.cancel()

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

@app.get("/healthz")
def health():
    return {"status": "ok", "service": "video-ltx-service"}
