"""Ingestion gateway — dual-mode adapter for live vs. mock document ingestion.

When LIVE_INGESTION_MODE is enabled, all operations proxy to the real
LightRAG API via ``lightrag_client``.  When disabled (default), operations
return deterministic mock responses so the frontend contract tests keep
working without external services.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from uuid import uuid4

from api.clients.lightrag_client import LightRAGClient
from api.config import settings


class IngestionGateway:
    """Adapter between the workspace service and real ingestion infrastructure."""

    def __init__(self, *, live: bool | None = None) -> None:
        self.live = live if live is not None else settings.LIVE_INGESTION_MODE
        self._client: LightRAGClient | None = None

    @property
    def client(self) -> LightRAGClient:
        if self._client is None:
            self._client = LightRAGClient()
        return self._client

    # ── File ingestion ──

    def stage_file(self, filename: str, content: bytes) -> str:
        """Save uploaded file bytes to a staging directory and return the path."""
        staging_dir = Path(settings.UPLOAD_STAGING_DIR)
        staging_dir.mkdir(parents=True, exist_ok=True)
        unique_name = f"{uuid4().hex[:8]}_{filename}"
        dest = staging_dir / unique_name
        dest.write_bytes(content)
        return str(dest)

    def ingest_file(self, staged_path: str, metadata: dict | None = None) -> dict:
        """Ingest a staged file into the knowledge base.

        Args:
            staged_path: Absolute path to the file saved by ``stage_file``.
            metadata: Optional metadata dict (title, tags, etc.).

        Returns:
            A dict with ``track_id``, ``status``, and ``source`` at minimum.
        """
        if not self.live:
            return {
                "track_id": f"mock-track-{uuid4().hex[:8]}",
                "status": "accepted",
                "source": "mock-backed",
            }

        result = self.client.upload_file(staged_path)
        return {
            "track_id": result.get("track_id", f"live-{uuid4().hex[:8]}"),
            "doc_id": result.get("doc_id"),
            "status": "accepted",
            "source": "lightrag",
            "raw": result,
        }

    # ── Text ingestion ──

    def ingest_text(self, text: str, source: str | None = None) -> dict:
        """Insert raw text into the knowledge base."""
        if not self.live:
            return {
                "track_id": f"mock-track-{uuid4().hex[:8]}",
                "status": "accepted",
                "source": "mock-backed",
            }

        result = self.client.insert_text(text, source=source)
        return {
            "track_id": result.get("track_id", f"live-{uuid4().hex[:8]}"),
            "status": "accepted",
            "source": "lightrag",
            "raw": result,
        }

    # ── Reindex / scan ──

    def trigger_reindex(self, doc_id: str | None = None) -> dict:
        """Trigger reindexing / scan of the knowledge base."""
        if not self.live:
            return {
                "status": "accepted",
                "source": "mock-backed",
                "message": "Reindex simulated in mock mode.",
            }

        result = self.client.trigger_scan()
        return {
            "status": "accepted",
            "source": "lightrag",
            "raw": result,
        }

    # ── Health ──

    def check_health(self) -> dict:
        """Check health of the ingestion backend."""
        if not self.live:
            return {"status": "healthy", "source": "mock-backed"}

        return self.client.health()

    # ── Cleanup ──

    def cleanup_staged_file(self, staged_path: str) -> None:
        """Remove a staged file after ingestion is complete."""
        try:
            Path(staged_path).unlink(missing_ok=True)
        except OSError:
            pass
