"""
Configuration settings for Admin Dashboard API.

Loads from environment variables with sensible defaults.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


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

    # File Upload
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(Path(__file__).parent.parent / "uploads"))
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", str(50 * 1024 * 1024)))  # 50MB
    ALLOWED_EXTENSIONS: set = {".pdf", ".txt", ".md", ".docx"}

    # CORS
    CORS_ORIGINS: list = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")

    # SSO provider handoff
    SSO_PROVIDER_MODE: str = os.getenv("SSO_PROVIDER_MODE", "emulator")
    SSO_PROVIDER_NAME: str = os.getenv("SSO_PROVIDER_NAME", "UIT Institutional SSO")
    SSO_AUTHORIZE_URL: str = os.getenv("SSO_AUTHORIZE_URL", "")
    SSO_CLIENT_ID: str = os.getenv("SSO_CLIENT_ID", "")
    SSO_SCOPE: str = os.getenv("SSO_SCOPE", "openid profile email groups")
    SSO_CALLBACK_BASE_URL: str = os.getenv("SSO_CALLBACK_BASE_URL", "")
    SSO_ROLE_CLAIM: str = os.getenv("SSO_ROLE_CLAIM", "role")
    SSO_GROUP_CLAIM: str = os.getenv("SSO_GROUP_CLAIM", "groups")
    SSO_EMAIL_CLAIM: str = os.getenv("SSO_EMAIL_CLAIM", "email")
    SSO_GROUP_ROLE_MAP: str = os.getenv("SSO_GROUP_ROLE_MAP", "")
    SSO_ROLE_HINT_MAP: str = os.getenv(
        "SSO_ROLE_HINT_MAP",
        "lecturer:lecturer,operator:operator,admin:admin",
    )


settings = Settings()
