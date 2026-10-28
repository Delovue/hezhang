import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.script import ScriptDirectory
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import activities, auth, expenses, payments, reports, settlement
from app.config import Settings
from app.database import build_engine, transaction
from app.domain.errors import (
    DomainError,
    InvalidInputError,
    PermissionDeniedError,
    StateConflictError,
)
from app.errors import API_ERROR_RESPONSES, ApiError, ErrorCode, error_response

logger = logging.getLogger(__name__)

DOMAIN_ERROR_STATUS = {
    InvalidInputError: 422,
    PermissionDeniedError: 403,
    StateConflictError: 409,
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    expected_revision = ScriptDirectory(
        str(Path(__file__).resolve().parents[1] / "migrations")
    ).get_current_head()
    if expected_revision is None:
        raise RuntimeError("No database migration is configured")
    engine = build_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        engine.dispose()

    app = FastAPI(
        title="合账基础后端",
        version="0.1.0",
        lifespan=lifespan,
        description="认证、活动、成员、费用与审计（乙）；分摊预览、余额、结算与付款（丙）。金额单位为分。",
    )
    app.state.settings = settings
    app.state.engine = engine
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Retry-After"],
    )
    for module in [auth, activities, expenses, settlement, payments, reports]:
        app.include_router(module.router, prefix="/api/v1", responses=API_ERROR_RESPONSES)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException):
        code = (
            exc.code
            if isinstance(exc, ApiError)
            else {
                404: ErrorCode.NOT_FOUND,
                405: ErrorCode.METHOD_NOT_ALLOWED,
            }.get(exc.status_code, ErrorCode.HTTP_ERROR)
        )
        detail = exc.detail if isinstance(exc.detail, str) else "请求失败"
        return error_response(exc.status_code, code, detail, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        # Do not echo submitted passwords, tokens, or full request bodies.
        detail = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return error_response(422, ErrorCode.VALIDATION_ERROR, detail)

    @app.exception_handler(DomainError)
    async def domain_error(_request: Request, exc: DomainError):
        return error_response(DOMAIN_ERROR_STATUS[type(exc)], exc.code, exc.message)

    @app.exception_handler(IntegrityError)
    async def integrity_error(_request: Request, _exc: IntegrityError):
        return error_response(409, ErrorCode.DATA_CONFLICT, "数据冲突，请刷新后重试")

    @app.exception_handler(OperationalError)
    async def operational_error(_request: Request, exc: OperationalError):
        code = getattr(exc.orig, "sqlite_errorcode", 0) & 0xFF
        if code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
            return error_response(
                409,
                ErrorCode.DATABASE_BUSY,
                "账本正在更新，请稍后重试",
                retryable=True,
                headers={"Retry-After": "1"},
            )
        logger.error("Database operation failed: %s", type(exc.orig).__name__)
        return error_response(
            503, ErrorCode.DATABASE_NOT_READY, "数据库未就绪，请检查连接与数据库迁移"
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.error("Unhandled API error: %s", type(exc).__name__)
        response = error_response(
            500, ErrorCode.INTERNAL_ERROR, "服务暂时无法完成请求，请稍后查看账本"
        )
        # The server-error handler runs outside CORSMiddleware; allow the configured frontend
        # to read this JSON error, while retaining the same origin policy and no credentials.
        origin = request.headers.get("origin")
        if origin and (origin in settings.cors_origins or "*" in settings.cors_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response

    @app.get("/health", tags=["运行状态"])
    def health():
        try:
            with transaction(engine) as session:
                revisions = session.scalars(text("SELECT version_num FROM alembic_version")).all()
        except SQLAlchemyError:
            return JSONResponse(
                status_code=503, content={"status": "not_ready", "detail": "请先执行数据库迁移"}
            )
        if revisions != [expected_revision]:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "detail": "数据库结构与当前代码不匹配，请执行数据库迁移",
                    "expected_schema_revision": expected_revision,
                },
            )
        return {"status": "ok", "schema_revision": expected_revision}

    return app
