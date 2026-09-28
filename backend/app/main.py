"""XunkeFlow 后端入口。"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.utils.logger import logger
from app.api.routers import (auth, courses, files, knowledge, tests,
                              profiles, resources, agents, review, wrong,
                              questions, reports, admin, stats)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.started_at = datetime.now(timezone.utc)
    logger.info(
        "启动 %s | AI模式=%s | model=%s | db_backend=%s",
        settings.APP_NAME,
        settings.effective_llm_provider,
        settings.LLM_MODEL,
        settings.DATABASE_URL.split(":", 1)[0],
    )
    if settings.MODEL_POLICY_WARNING:
        logger.warning(settings.MODEL_POLICY_WARNING)
    if settings.LLM_PROVIDER == "deepseek" and not settings.deepseek_key_configured:
        logger.warning("已选择 DeepSeek，但 DEEPSEEK_API_KEY 未配置；当前使用演示模式。")
    init_db()
    if settings.AUTO_SEED_DEMO and settings.APP_ENV.lower() not in {"prod", "production"}:
        try:
            from app.database.seed import ensure_seed
            ensure_seed()
        except Exception as e:
            logger.warning(f"seed skipped: {e}")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="循课——多智能体协作的个性化学习平台",
    lifespan=lifespan,
    debug=settings.APP_DEBUG and not settings.is_production,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)
# Validate Host in every environment. This also protects direct-Uvicorn demo
# runs, where no reverse proxy exists to normalize malformed Host headers.
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.trusted_hosts_list or ["localhost", "127.0.0.1", "testserver"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Central browser hardening for API responses and report previews."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    # Use the raw ASGI path for security decisions. It cannot be reinterpreted
    # through a malformed Host header while Starlette reconstructs request.url.
    request_path = str(request.scope.get("path") or "")
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" in content_type and request_path.startswith("/api/reports/"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        )
    if request_path.startswith("/api/") and request_path != "/api/health":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health():
    from app.services.llm_client import llm_client
    return {"status": "ok", "app": settings.APP_NAME,
            "ai_mode": llm_client.mode,
            "is_mock": llm_client.is_mock}


@app.get("/api/system/info")
def system_info():
    from app.services.llm_client import llm_client
    status = llm_client.status()
    is_mock = status["mode"] == "demo"
    return {
        "app_name": settings.APP_NAME,
        "llm_provider": status["active_provider"],
        "requested_provider": status["requested_provider"],
        "llm_model": status["model"],
        "api_key_configured": status["api_key_configured"],
        "pro_models_allowed": False,
        "model_policy_enforced": True,
        "policy_warning": status["policy_warning"],
        "embedding_provider": "本地 TF-IDF / 中文关键词",
        "vector_store": "SQLite 持久化课程片段",
        "is_mock_llm": is_mock,
        "demo_mode": is_mock,
        "llm_active": not is_mock,
        "engine_name": "本地课程引擎" if is_mock else "在线智能生成服务",
        "engine_status": "demo" if is_mock else "real",
        "mode_label": "演示模式" if is_mock else "真实模型模式",
        "last_call": status["last_call"],
        "degraded": status["last_call"].get("fallback_used", False),
        "degraded_message": "真实模型调用失败，当前使用演示模式结果" if status["last_call"].get("fallback_used") else "",
    }


# 注册路由
for r in (auth, courses, files, knowledge, tests, profiles, resources,
          agents, review, wrong, questions, reports, admin, stats):
    app.include_router(r.router)

# 静态资源（上传文件访问，可选）
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


def _safe_frontend_file(frontend_root: Path, relative_path: str) -> Path | None:
    """Resolve a packaged frontend path without permitting traversal."""
    candidate = (frontend_root / relative_path).resolve()
    try:
        candidate.relative_to(frontend_root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


# A standalone desktop installer sets XUNKEFLOW_FRONTEND_DIR to the bundled
# Vite production output.  Register this catch-all only after every API router
# so it cannot shadow backend endpoints.  Browser history routes fall back to
# index.html, allowing refreshes on /teacher/*, /student/* and /admin/*.
_frontend_dir_raw = os.environ.get("XUNKEFLOW_FRONTEND_DIR", "").strip()
if _frontend_dir_raw:
    _frontend_dir = Path(_frontend_dir_raw).expanduser().resolve()
    _frontend_index = _frontend_dir / "index.html"
    if _frontend_index.is_file():
        _assets_dir = _frontend_dir / "assets"
        if _assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="desktop-assets")

        @app.get("/{frontend_path:path}", include_in_schema=False)
        async def desktop_frontend(frontend_path: str):
            requested = _safe_frontend_file(_frontend_dir, frontend_path)
            return FileResponse(str(requested or _frontend_index))
