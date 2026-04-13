"""
Configuration settings for Admin Dashboard API.

Loads from environment variables with sensible defaults.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def env_csv(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    """Application settings."""

    # API Settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8001"))

    # LightRAG API
    LIGHTRAG_URL: str = os.getenv("LIGHTRAG_URL", "http://localhost:9621")
    LIGHTRAG_API_KEY: str = os.getenv("LIGHTRAG_API_KEY", "")
    LIGHTRAG_USERNAME: str = os.getenv("LIGHTRAG_USERNAME", "admin")
    LIGHTRAG_PASSWORD: str = os.getenv("LIGHTRAG_PASSWORD", "admin")
    LIGHTRAG_PUBLIC_URL: str = os.getenv("LIGHTRAG_PUBLIC_URL", "").strip()
    LIGHTRAG_PUBLIC_USERNAME: str = os.getenv("LIGHTRAG_PUBLIC_USERNAME", os.getenv("LIGHTRAG_USERNAME", "admin"))
    LIGHTRAG_PUBLIC_PASSWORD: str = os.getenv("LIGHTRAG_PUBLIC_PASSWORD", os.getenv("LIGHTRAG_PASSWORD", "admin"))

    # File Upload
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(Path(__file__).parent.parent / "uploads"))
    UPLOAD_STAGING_DIR: str = os.getenv("UPLOAD_STAGING_DIR", str(Path(__file__).parent.parent / "uploads" / "staging"))
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", str(50 * 1024 * 1024)))  # 50MB
    ALLOWED_EXTENSIONS: set = {".pdf", ".txt", ".md", ".docx"}
    # Database: default SQLite for local dev.
    # For Postgres: WORKSPACE_DATABASE_URL=postgresql+psycopg2://admin_dashboard_app:change-me-admin-dashboard-password@localhost:5433/admin_dashboard
    WORKSPACE_DATABASE_URL: str = os.getenv(
        "WORKSPACE_DATABASE_URL",
        f"sqlite+pysqlite:///{(Path(__file__).parent.parent / 'data' / 'workspace.sqlite3').as_posix()}",
    )
    WORKSPACE_AUTO_SEED: bool = env_flag("WORKSPACE_AUTO_SEED", "true")

    # Live ingestion gateway: when true, upload/reindex call real LightRAG/LangGraph.
    # When false (default), existing mock/contract behavior is preserved.
    LIVE_INGESTION_MODE: bool = env_flag("LIVE_INGESTION_MODE", "false")

    # CORS
    CORS_ORIGINS: list = env_csv(
        "CORS_ORIGINS",
        "http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:5173,http://localhost:5173",
    )
    TRUSTED_HOSTS: list = env_csv("TRUSTED_HOSTS", "")
    FORCE_HTTPS_REDIRECT: bool = env_flag("FORCE_HTTPS_REDIRECT", "false")

    # Runtime security
    TEST_MODE: bool = env_flag("TEST_MODE", "false")
    EXPOSE_ERROR_DETAILS: bool = env_flag("EXPOSE_ERROR_DETAILS", "false")
    SESSION_COOKIE_SECURE: bool = env_flag("SESSION_COOKIE_SECURE", "false")
    SESSION_COOKIE_SAMESITE: str = os.getenv("SESSION_COOKIE_SAMESITE", "lax").strip().lower()
    SESSION_COOKIE_DOMAIN: str = os.getenv("SESSION_COOKIE_DOMAIN", "").strip()
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60"))
    AUTH_RATE_LIMIT_MAX_REQUESTS: int = int(os.getenv("AUTH_RATE_LIMIT_MAX_REQUESTS", "20"))

    # SSO provider handoff
    SSO_PROVIDER_MODE: str = os.getenv("SSO_PROVIDER_MODE", "emulator")
    SSO_PROVIDER_NAME: str = os.getenv("SSO_PROVIDER_NAME", "Google Workspace UIT")
    SSO_AUTHORIZE_URL: str = os.getenv("SSO_AUTHORIZE_URL", "https://accounts.google.com/o/oauth2/v2/auth")
    SSO_TOKEN_URL: str = os.getenv("SSO_TOKEN_URL", "https://oauth2.googleapis.com/token")
    SSO_USERINFO_URL: str = os.getenv("SSO_USERINFO_URL", "https://openidconnect.googleapis.com/v1/userinfo")
    SSO_CLIENT_ID: str = os.getenv("SSO_CLIENT_ID", "")
    SSO_CLIENT_SECRET: str = os.getenv("SSO_CLIENT_SECRET", "")
    SSO_SCOPE: str = os.getenv("SSO_SCOPE", "openid email profile")
    SSO_HOSTED_DOMAIN: str = os.getenv("SSO_HOSTED_DOMAIN", "gm.uit.edu.vn")
    SSO_CALLBACK_BASE_URL: str = os.getenv("SSO_CALLBACK_BASE_URL", "")
    SSO_FRONTEND_BASE_URL: str = os.getenv("SSO_FRONTEND_BASE_URL", "http://127.0.0.1:3000")
    SSO_ROLE_CLAIM: str = os.getenv("SSO_ROLE_CLAIM", "role")
    SSO_GROUP_CLAIM: str = os.getenv("SSO_GROUP_CLAIM", "groups")
    SSO_EMAIL_CLAIM: str = os.getenv("SSO_EMAIL_CLAIM", "email")
    SSO_GROUP_ROLE_MAP: str = os.getenv("SSO_GROUP_ROLE_MAP", "")
    SSO_ROLE_HINT_MAP: str = os.getenv(
        "SSO_ROLE_HINT_MAP",
        "teacher:teacher,admin:admin",
    )
    ENABLE_DEMO_AUTH: bool = env_flag("ENABLE_DEMO_AUTH", "false")


settings = Settings()
