"""Core building blocks for ``Admin_Backend``.

Currently exposes the :mod:`errors` envelope and the :mod:`settings`
module used by the FastAPI ``lifespan`` startup guard.
"""

from .errors import (
    Structured_Error,
    StructuredError,
    StructuredErrorCode,
)
from .settings import (
    LangGraphUpstreamConfigError,
    Settings,
    get_settings,
)

__all__ = [
    "LangGraphUpstreamConfigError",
    "Settings",
    "StructuredError",
    "StructuredErrorCode",
    "Structured_Error",
    "get_settings",
]
