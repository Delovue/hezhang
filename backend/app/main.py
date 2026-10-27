import logging
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from app.api import activities, auth
from app.config import Settings
from app.database import build_engine, transaction

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = build_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        engine.dispose()

    app = FastAPI(
        title="合账基础后端",
        version="0.1.0",
        lifespan=lifespan,
        description="角色乙：认证、活动、成员、费用与审计。金额单位为分。",
    )
    app.state.settings = settings
    app.state.engine = engine
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(activities.router, prefix="/api/v1")

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        # Do not echo submitted passwords, tokens, or full request bodies.
        detail = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(IntegrityError)
    async def integrity_error(_request: Request, _exc: IntegrityError):
        return JSONResponse(status_code=409, content={"detail": "数据冲突，请刷新后重试"})

    @app.exception_handler(OperationalError)
    async def operational_error(_request: Request, exc: OperationalError):
        code = getattr(exc.orig, "sqlite_errorcode", 0) & 0xFF
        if code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
            return JSONResponse(status_code=409, content={"detail": "账本正在更新，请稍后重试"})
        logger.error("Database operation failed: %s", type(exc.orig).__name__)
        return JSONResponse(
            status_code=503, content={"detail": "数据库未就绪，请检查连接与数据库迁移"}
        )

    @app.get("/health", tags=["运行状态"])
    def health():
        try:
            with transaction(engine) as session:
                revision = session.scalar(text("SELECT version_num FROM alembic_version"))
            if not revision:
                raise ValueError("No schema revision")
        except (SQLAlchemyError, ValueError):
            return JSONResponse(
                status_code=503, content={"status": "not_ready", "detail": "请先执行数据库迁移"}
            )
        return {"status": "ok", "schema_revision": revision}

    return app
