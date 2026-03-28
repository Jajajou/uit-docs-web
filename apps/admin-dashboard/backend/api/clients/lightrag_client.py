"""
LightRAG API Client for Admin Dashboard.

Simplified client to proxy requests to LightRAG API.
"""

import os

import requests
from dotenv import load_dotenv

from api.config import settings

load_dotenv()

DEFAULT_TIMEOUT = 60


class LightRAGClient:
    """Client for LightRAG API operations."""

    def __init__(self):
        """Initialize client with settings."""
        self.base_url = settings.LIGHTRAG_URL
        self.session = requests.Session()
        self.access_token: str | None = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with LightRAG API."""
        try:
            resp = self.session.post(
                f"{self.base_url}/login",
                data={
                    "username": settings.LIGHTRAG_USERNAME,
                    "password": settings.LIGHTRAG_PASSWORD,
                },
                timeout=DEFAULT_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token")
        except Exception:
            # Silent fail - will work without auth if LightRAG allows
            pass

    def _headers(self) -> dict:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def health(self) -> dict:
        """Check LightRAG health."""
        try:
            resp = self.session.get(
                f"{self.base_url}/health",
                timeout=DEFAULT_TIMEOUT,
            )
            return resp.json() if resp.ok else {"status": "unhealthy"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def upload_file(self, file_path: str) -> dict:
        """Upload a file to LightRAG."""
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            headers = {}
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
            resp = self.session.post(
                f"{self.base_url}/documents/upload",
                files=files,
                headers=headers,
                timeout=DEFAULT_TIMEOUT * 2,
            )
        return resp.json() if resp.ok else {"error": resp.text}

    def insert_text(self, text: str, source: str | None = None) -> dict:
        """Insert text directly to LightRAG."""
        payload = {"text": text}
        if source:
            payload["file_source"] = source
        resp = self.session.post(
            f"{self.base_url}/documents/text",
            json=payload,
            headers=self._headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        return resp.json() if resp.ok else {"error": resp.text}

    def get_documents(
        self,
        page: int = 1,
        page_size: int = 50,
        status_filter: str | None = None,
    ) -> dict:
        """Get paginated documents list."""
        params = {
            "page": page,
            "page_size": page_size,
            "sort_field": "updated_at",
            "sort_direction": "desc",
        }
        if status_filter:
            params["status_filter"] = status_filter
        resp = self.session.get(
            f"{self.base_url}/documents",
            params=params,
            headers=self._headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        return resp.json() if resp.ok else {"error": resp.text, "documents": []}

    def delete_document(self, doc_ids: list[str]) -> dict:
        """Delete documents by IDs."""
        resp = self.session.delete(
            f"{self.base_url}/documents",
            json={"doc_ids": doc_ids, "delete_file": False},
            headers=self._headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        return resp.json() if resp.ok else {"error": resp.text}

    def trigger_scan(self) -> dict:
        """Trigger document scan/reindex."""
        resp = self.session.post(
            f"{self.base_url}/documents/scan",
            headers=self._headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        return resp.json() if resp.ok else {"error": resp.text}

    def get_status_counts(self) -> dict:
        """Get document status counts for analytics."""
        resp = self.session.get(
            f"{self.base_url}/documents/status-counts",
            headers=self._headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        return resp.json() if resp.ok else {"error": resp.text}

    def get_pipeline_status(self) -> dict:
        """Get pipeline processing status."""
        resp = self.session.get(
            f"{self.base_url}/documents/pipeline-status",
            headers=self._headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        return resp.json() if resp.ok else {"error": resp.text}

    def get_graph_labels(self, limit: int = 300) -> dict:
        """Get popular graph labels."""
        resp = self.session.get(
            f"{self.base_url}/graph/labels/popular",
            params={"limit": limit},
            headers=self._headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        return resp.json() if resp.ok else {"error": resp.text}


# Singleton instance
lightrag_client = LightRAGClient()
