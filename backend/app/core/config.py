"""全局配置。

所有敏感配置只从项目根目录 ``.env`` 读取。DeepSeek 采用白名单策略：
无论外部如何填写，真正发往远端的模型都只能是 ``deepseek-v4-flash``。
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import List
from urllib.parse import urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

def _resolve_base_dir(config_file: Path) -> Path:
    """Resolve the application root in both source and container layouts.

    Local source: ``<project>/backend/app/core/config.py`` -> ``<project>``.
    Docker image: ``/app/app/core/config.py`` -> ``/app``.
    """
    backend_or_app_root = config_file.resolve().parents[2]
    if backend_or_app_root.name == "backend":
        return backend_or_app_root.parent
    return backend_or_app_root


SOURCE_BASE_DIR = _resolve_base_dir(Path(__file__))
# Desktop installers keep immutable course assets inside the application and
# all mutable state in the current user's application-data directory.  Source
# and Docker runs keep the historical project-root defaults.
BASE_DIR = Path(os.environ.get("XUNKEFLOW_ASSET_DIR", str(SOURCE_BASE_DIR))).expanduser().resolve()
DATA_DIR = Path(os.environ.get("XUNKEFLOW_DATA_DIR", str(BASE_DIR / "data"))).expanduser().resolve()
ENV_FILE = Path(os.environ.get("XUNKEFLOW_ENV_FILE", str(BASE_DIR / ".env"))).expanduser().resolve()
DEEPSEEK_FLASH_MODEL = "deepseek-v4-flash"


def validate_deepseek_model(value: object) -> str:
    """Return the only allowed outbound model or reject the configuration.

    A Pro model must never be silently rewritten to Flash: doing so hides an
    invalid production configuration and makes the model-status page report a
    policy success that was never actually configured. Runtime API failures may
    still fall back to the clearly labelled Mock provider; model policy errors
    are configuration errors and therefore fail fast.
    """
    requested = str(value or DEEPSEEK_FLASH_MODEL).strip()
    if "pro" in requested.lower():
        raise ValueError(f"禁止使用 DeepSeek Pro 模型：{requested}")
    if requested != DEEPSEEK_FLASH_MODEL:
        raise ValueError(f"DeepSeek 模型白名单仅允许 {DEEPSEEK_FLASH_MODEL}")
    return DEEPSEEK_FLASH_MODEL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        # Validation failures can be printed by the process manager during a
        # fail-fast startup. Never include the full environment payload there.
        hide_input_in_errors=True,
    )

    # 应用
    APP_NAME: str = "XunkeFlow"
    APP_ENV: str = "dev"
    APP_DEBUG: bool = False
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    APP_TIMEZONE: str = "Asia/Shanghai"
    AUTO_SEED_DEMO: bool = True

    # 数据库
    DATABASE_URL: str = f"sqlite:///{DATA_DIR}/xunkeflow.db"

    # JWT
    JWT_SECRET: str = "xunkeflow-default-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    JWT_ISSUER: str = "xunkeflow"
    JWT_AUDIENCE: str = "xunkeflow-web"

    # Authentication abuse controls. The application enforces failed-login and
    # public-registration limits even when it is run without the nginx layer.
    AUTH_LOGIN_MAX_FAILURES: int = 5
    AUTH_LOGIN_WINDOW_SECONDS: int = 300
    AUTH_REGISTER_MAX_REQUESTS: int = 10
    AUTH_REGISTER_WINDOW_SECONDS: int = 3600

    # 文件
    UPLOAD_DIR: str = str(DATA_DIR / "uploads")
    CHUNK_DIR: str = str(DATA_DIR / "chunks")
    MAX_UPLOAD_MB: int = 50

    # 课程片段检索：SQLite 持久化 + 本地 TF-IDF/中文关键词。
    VECTOR_STORE: str = "sqlite_tfidf"

    # LLM：当前生产路径只开放 mock / deepseek。
    LLM_PROVIDER: str = "mock"
    LLM_MODEL: str = DEEPSEEK_FLASH_MODEL
    LLM_TIMEOUT: int = 60
    LLM_MAX_RETRIES: int = 2
    LLM_TEMPERATURE: float = 0.4
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_API_KEY: str = ""
    MODEL_POLICY_WARNING: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    TRUSTED_HOSTS: str = "localhost,127.0.0.1,testserver"

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _split_cors(cls, v: str) -> str:
        return v

    @field_validator("LLM_PROVIDER", mode="before")
    @classmethod
    def _normalize_provider(cls, value: str) -> str:
        provider = str(value or "mock").strip().lower()
        if provider not in {"mock", "deepseek"}:
            raise ValueError("LLM_PROVIDER 当前只允许 mock 或 deepseek")
        return provider

    @field_validator("DEEPSEEK_BASE_URL", mode="before")
    @classmethod
    def _normalize_base_url(cls, value: str) -> str:
        raw = str(value or "https://api.deepseek.com").strip().rstrip("/")
        parsed = urlsplit(raw)
        # The backend sends the bearer credential to this origin. Restricting it
        # to the official HTTPS endpoint prevents accidental key disclosure via
        # a typo, an insecure proxy, or a hostile environment override.
        if (
            parsed.scheme.lower() != "https"
            or parsed.hostname != "api.deepseek.com"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/", "/v1"}
        ):
            raise ValueError("DEEPSEEK_BASE_URL 仅允许 DeepSeek 官方 HTTPS 地址")
        path = "/v1" if parsed.path == "/v1" else ""
        return urlunsplit(("https", "api.deepseek.com", path, "", ""))

    @field_validator("JWT_ALGORITHM", mode="before")
    @classmethod
    def _valid_jwt_algorithm(cls, value: str) -> str:
        # This single-service deployment intentionally uses one fixed symmetric
        # algorithm. Rejecting environment-controlled alternatives prevents
        # algorithm confusion and keeps the unused ECDSA dependency off-path.
        algorithm = str(value or "HS256").strip().upper()
        if algorithm != "HS256":
            raise ValueError("JWT_ALGORITHM 仅允许 HS256")
        return algorithm

    @field_validator("JWT_EXPIRE_MINUTES")
    @classmethod
    def _valid_jwt_expiry(cls, value: int) -> int:
        # Browser bearer tokens are JavaScript-readable in the current SPA
        # architecture, so cap their lifetime even if an old .env requested a
        # full day. Eight hours covers a competition/demo session.
        return max(5, min(int(value), 480))

    @field_validator("LLM_TIMEOUT")
    @classmethod
    def _valid_timeout(cls, value: int) -> int:
        return max(5, min(int(value), 180))

    @field_validator("LLM_MAX_RETRIES")
    @classmethod
    def _valid_retries(cls, value: int) -> int:
        return max(0, min(int(value), 5))

    @field_validator("LLM_TEMPERATURE")
    @classmethod
    def _valid_temperature(cls, value: float) -> float:
        return max(0.0, min(float(value), 1.0))

    @field_validator("AUTH_LOGIN_MAX_FAILURES")
    @classmethod
    def _valid_login_failures(cls, value: int) -> int:
        return max(3, min(int(value), 20))

    @field_validator("AUTH_LOGIN_WINDOW_SECONDS")
    @classmethod
    def _valid_login_window(cls, value: int) -> int:
        return max(60, min(int(value), 3600))

    @field_validator("AUTH_REGISTER_MAX_REQUESTS")
    @classmethod
    def _valid_register_requests(cls, value: int) -> int:
        return max(3, min(int(value), 100))

    @field_validator("AUTH_REGISTER_WINDOW_SECONDS")
    @classmethod
    def _valid_register_window(cls, value: int) -> int:
        return max(60, min(int(value), 86400))

    @model_validator(mode="after")
    def _enforce_deepseek_flash(self):
        self.LLM_MODEL = validate_deepseek_model(self.LLM_MODEL)
        self.MODEL_POLICY_WARNING = ""
        if self.APP_ENV.strip().lower() in {"prod", "production"}:
            weak_secrets = {
                "xunkeflow-default-secret-change-me",
                "xunkeflow-jwt-secret-change-in-production-2026",
                "xunkeflow-local-only-change-before-production",
                "replace-with-a-random-string-at-least-32-characters",
            }
            if len(self.JWT_SECRET.strip()) < 32 or self.JWT_SECRET.strip() in weak_secrets:
                raise ValueError("生产环境必须配置至少 32 位的随机 JWT_SECRET")
            if not self.JWT_ISSUER.strip() or not self.JWT_AUDIENCE.strip():
                raise ValueError("生产环境必须配置 JWT_ISSUER 与 JWT_AUDIENCE")
            hosts = [host.strip() for host in self.TRUSTED_HOSTS.split(",") if host.strip()]
            if not hosts or "*" in hosts:
                raise ValueError("生产环境必须配置明确的 TRUSTED_HOSTS，禁止使用通配符")
            origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
            if "*" in origins:
                raise ValueError("生产环境 CORS_ORIGINS 禁止使用通配符")
        if self.DATABASE_URL.startswith("sqlite:///./"):
            relative_db = self.DATABASE_URL.removeprefix("sqlite:///./")
            self.DATABASE_URL = f"sqlite:///{(BASE_DIR / relative_db).resolve()}"
        for field_name in ("UPLOAD_DIR", "CHUNK_DIR"):
            value = Path(str(getattr(self, field_name))).expanduser()
            if not value.is_absolute():
                setattr(self, field_name, str((BASE_DIR / value).resolve()))
        return self

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def trusted_hosts_list(self) -> List[str]:
        return [host.strip() for host in self.TRUSTED_HOSTS.split(",") if host.strip() and host.strip() != "*"]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() in {"prod", "production"}

    @property
    def deepseek_key_configured(self) -> bool:
        return bool(self.DEEPSEEK_API_KEY.strip())

    @property
    def effective_llm_provider(self) -> str:
        if self.LLM_PROVIDER == "deepseek" and self.deepseek_key_configured:
            return "deepseek"
        return "mock"

    def ensure_dirs(self) -> None:
        for d in (DATA_DIR, Path(self.UPLOAD_DIR), Path(self.CHUNK_DIR)):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s


settings = get_settings()
