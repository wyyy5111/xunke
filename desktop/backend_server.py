#!/usr/bin/env python3
"""Standalone XunkeFlow backend used by the desktop installers.

Electron supplies the application asset, frontend and user-data directories.
This process configures those paths before importing FastAPI, then serves both
the API and the compiled Vue SPA from one loopback-only HTTP endpoint.
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path


APP_NAME = "XunkeFlow"


def _bundle_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root).resolve()
    return Path(__file__).resolve().parent.parent


def _user_root() -> Path:
    supplied = os.environ.get("XUNKEFLOW_USER_DATA_DIR", "").strip()
    if supplied:
        return Path(supplied).expanduser().resolve()
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / APP_NAME).resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return (base / APP_NAME).resolve()
    base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return (base / "xunkeflow").resolve()


def _ensure_local_config(config_file: Path) -> None:
    if config_file.exists():
        return
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
        "\n".join(
            [
                "# XunkeFlow desktop local configuration",
                "APP_ENV=desktop",
                "APP_DEBUG=false",
                "AUTO_SEED_DEMO=true",
                f"JWT_SECRET={secrets.token_urlsafe(48)}",
                "JWT_ALGORITHM=HS256",
                "JWT_EXPIRE_MINUTES=480",
                "JWT_ISSUER=xunkeflow",
                "JWT_AUDIENCE=xunkeflow-web",
                "VECTOR_STORE=sqlite_tfidf",
                "LLM_PROVIDER=mock",
                "LLM_MODEL=deepseek-v4-flash",
                "DEEPSEEK_BASE_URL=https://api.deepseek.com",
                "DEEPSEEK_API_KEY=",
                "LLM_TIMEOUT=60",
                "LLM_MAX_RETRIES=2",
                "LLM_TEMPERATURE=0.4",
                "",
            ]
        ),
        encoding="utf-8",
    )
    try:
        config_file.chmod(0o600)
    except OSError:
        pass


def configure_environment() -> tuple[str, int, Path]:
    bundle_root = _bundle_root()
    user_root = _user_root()
    data_dir = user_root / "data"
    log_dir = user_root / "logs"
    for directory in (data_dir, data_dir / "uploads", data_dir / "chunks", log_dir):
        directory.mkdir(parents=True, exist_ok=True)

    config_file = user_root / ".env"
    _ensure_local_config(config_file)

    frontend_dir = Path(
        os.environ.get("XUNKEFLOW_FRONTEND_DIR", str(bundle_root / "frontend_dist"))
    ).expanduser().resolve()
    asset_dir = Path(
        os.environ.get("XUNKEFLOW_ASSET_DIR", str(bundle_root))
    ).expanduser().resolve()

    host = "127.0.0.1"
    port = int(os.environ.get("APP_PORT", "8173"))
    runtime_env = {
        "XUNKEFLOW_ASSET_DIR": str(asset_dir),
        "XUNKEFLOW_DATA_DIR": str(data_dir),
        "XUNKEFLOW_ENV_FILE": str(config_file),
        "XUNKEFLOW_FRONTEND_DIR": str(frontend_dir),
        "DATABASE_URL": f"sqlite:///{data_dir / 'xunkeflow.db'}",
        "UPLOAD_DIR": str(data_dir / "uploads"),
        "CHUNK_DIR": str(data_dir / "chunks"),
        "APP_HOST": host,
        "APP_PORT": str(port),
        "CORS_ORIGINS": f"http://{host}:{port}",
        "TRUSTED_HOSTS": "127.0.0.1,localhost",
    }
    for key, value in runtime_env.items():
        os.environ[key] = value
    return host, port, log_dir / "backend.log"


def main() -> None:
    host, port, log_file = configure_environment()
    # Import only after every path/security environment variable is fixed.
    import uvicorn
    from app.main import app

    log_config = uvicorn.config.LOGGING_CONFIG.copy()
    for formatter in log_config.get("formatters", {}).values():
        formatter["fmt"] = "%(asctime)s | %(levelprefix)s %(message)s"
    with log_file.open("a", encoding="utf-8") as log_stream:
        # PyInstaller windowed builds have no usable stdout/stderr.  Preserve a
        # local troubleshooting log without ever logging environment secrets.
        if sys.stdout is None:
            sys.stdout = log_stream
        if sys.stderr is None:
            sys.stderr = log_stream
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_config=log_config,
            access_log=False,
            server_header=False,
        )


if __name__ == "__main__":
    main()
