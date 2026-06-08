import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.response import generate_request_id


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or generate_request_id()
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


register_exception_handlers(app)
app.include_router(api_v1_router, prefix="/api/v1")


# ── EventBus 生命周期管理 ──
@app.on_event("startup")
async def start_event_bus() -> None:
    from app.core.event_bus import get_event_bus
    from app.core.event_handlers import register_default_handlers

    register_default_handlers()
    bus = get_event_bus()
    await bus.start()


@app.on_event("startup")
async def setup_pgvector() -> None:
    """尝试在启动时设置 pgvector 扩展和索引。"""
    try:
        from app.db.pgvector_setup import setup_pgvector
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            result = await setup_pgvector(db)
            if result["extension_available"]:
                import logging
                logging.getLogger(__name__).info("pgvector setup: %s", result)
    except Exception:
        # pgvector 设置失败不应阻止应用启动
        pass


@app.on_event("shutdown")
async def stop_event_bus() -> None:
    from app.core.event_bus import get_event_bus

    bus = get_event_bus()
    await bus.stop()


@app.get("/")
async def root() -> dict[str, object]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "message": "Backend API is running. Open the student app at http://127.0.0.1:3000/.",
        "api_base": "/api/v1",
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
