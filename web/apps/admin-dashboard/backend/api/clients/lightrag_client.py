"""LightRAG API clients for the admin dashboard backend.

The dashboard uses two logical retrieval surfaces:
- internal: teacher/admin retrieval and ingestion
- public: student/guest retrieval over approved public documents only
"""

from __future__ import annotations

import os
from typing import Literal

import requests
from dotenv import load_dotenv

from api.config import settings

load_dotenv()

DEFAULT_TIMEOUT = 60


class LightRAGClient:
    """Client for LightRAG API operations."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.LIGHTRAG_URL).rstrip("/")
        self.username = username or settings.LIGHTRAG_USERNAME
        self.password = password or settings.LIGHTRAG_PASSWORD
        self.session = requests.Session()
        self.access_token: str | None = None
        self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate with LightRAG API."""
        try:
            response = self.session.post(
                f"{self.base_url}/login",
                data={
                    "username": self.username,
                    "password": self.password,
                },
                timeout=DEFAULT_TIMEOUT,
            )
            if response.status_code == 200:
                self.access_token = response.json().get("access_token")
        except Exception:
            # Silent fail: some local deployments run without auth enabled.
            pass

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def health(self) -> dict:
        """Check LightRAG health."""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=DEFAULT_TIMEOUT)
            return response.json() if response.ok else {"status": "unhealthy"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def upload_file(self, file_path: str) -> dict:
        """Upload a file to LightRAG."""
        with open(file_path, "rb") as handle:
            files = {"file": (os.path.basename(file_path), handle)}
            headers: dict[str, str] = {}
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
            response = self.session.post(
                f"{self.base_url}/documents/upload",
                files=files,
                headers=headers,
                timeout=DEFAULT_TIMEOUT * 2,
            )
        return response.json() if response.ok else {"error": response.text}

    def insert_text(self, text: str, source: str | None = None) -> dict:
        """Insert text directly to LightRAG."""
        payload = {"text": text}
        if source:
            payload["file_source"] = source
        response = self.session.post(
            f"{self.base_url}/documents/text",
            json=payload,
            headers=self._headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        return response.json() if response.ok else {"error": response.text}

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
        response = self.session.get(
            f"{self.base_url}/documents",
            params=params,
            headers=self._headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        return response.json() if response.ok else {"error": response.text, "documents": []}

    @staticmethod
    def extract_documents(result: dict | None) -> list[dict]:
        """Flatten LightRAG document payloads across legacy and status-grouped shapes."""
        if not isinstance(result, dict):
            return []
        documents = result.get("documents")
        if isinstance(documents, list):
            return [document for document in documents if isinstance(document, dict)]
        statuses = result.get("statuses")
        if isinstance(statuses, dict):
            flattened: list[dict] = []
            for entries in statuses.values():
                if isinstance(entries, list):
                    flattened.extend(document for document in entries if isinstance(document, dict))
            return flattened
        return []

    def find_documents_by_file_path(
        self,
        file_path: str,
        *,
        page_size: int = 200,
        max_pages: int = 10,
    ) -> list[dict]:
        """Resolve LightRAG documents by file source/path, including status metadata."""
        matches: list[dict] = []
        page = 1
        while page <= max_pages:
            result = self.get_documents(page=page, page_size=page_size)
            documents = self.extract_documents(result)
            if not documents:
                break
            for document in documents:
                normalized_path = str(document.get("file_path") or document.get("file_source") or "").strip()
                if normalized_path == file_path:
                    matches.append(document)
            pagination = result.get("pagination") if isinstance(result, dict) else {}
            if not isinstance(pagination, dict) or not pagination.get("has_next"):
                break
            page += 1
        return matches

    def find_document_ids_by_file_path(
        self,
        file_path: str,
        *,
        page_size: int = 200,
        max_pages: int = 10,
    ) -> list[str]:
        """Resolve LightRAG document ids by file source/path."""
        return [
            document_id
            for document in self.find_documents_by_file_path(
                file_path,
                page_size=page_size,
                max_pages=max_pages,
            )
            if (document_id := str(document.get("id") or "").strip())
        ]

    def delete_document(self, doc_ids: list[str]) -> dict:
        """Delete documents by ids."""
        response = self.session.delete(
            f"{self.base_url}/documents",
            json={"doc_ids": doc_ids, "delete_file": False},
            headers=self._headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        return response.json() if response.ok else {"error": response.text}

    def trigger_scan(self) -> dict:
        """Trigger document scan/reindex."""
        response = self.session.post(
            f"{self.base_url}/documents/scan",
            headers=self._headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        return response.json() if response.ok else {"error": response.text}

    def get_status_counts(self) -> dict:
        """Get document status counts for analytics."""
        response = self.session.get(
            f"{self.base_url}/documents/status_counts",
            headers=self._headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        return response.json() if response.ok else {"error": response.text}

    def get_pipeline_status(self) -> dict:
        """Get pipeline processing status."""
        response = self.session.get(
            f"{self.base_url}/documents/pipeline_status",
            headers=self._headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        return response.json() if response.ok else {"error": response.text}

    def get_graph_labels(self, limit: int = 300) -> dict:
        """Get popular graph labels."""
        response = self.session.get(
            f"{self.base_url}/graph/label/popular",
            params={"limit": limit},
            headers=self._headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        return response.json() if response.ok else {"error": response.text}

    def query_text(
        self,
        query: str,
        *,
        conversation_history: list[dict] | None = None,
        mode: str = "mix",
        response_type: str = "Multiple Paragraphs",
        include_references: bool = True,
        include_chunk_content: bool = False,
    ) -> dict:
        """Run a non-streaming LightRAG query."""
        payload: dict = {
            "query": query,
            "mode": mode,
            "include_references": include_references,
            "include_chunk_content": include_chunk_content,
            "response_type": response_type,
        }
        if conversation_history:
            payload["conversation_history"] = conversation_history
        try:
            response = self.session.post(
                f"{self.base_url}/query",
                json=payload,
                headers=self._headers(),
                timeout=DEFAULT_TIMEOUT * 2,
            )
        except Exception as exc:
            return {"error": str(exc)}
        return response.json() if response.ok else {"error": response.text, "status_code": response.status_code}


_lightrag_clients: dict[str, LightRAGClient] = {}


def get_lightrag_client(kind: Literal["internal", "public"] = "internal") -> LightRAGClient:
    if kind not in _lightrag_clients:
        if kind == "public":
            _lightrag_clients[kind] = LightRAGClient(
                base_url=settings.LIGHTRAG_PUBLIC_URL or settings.LIGHTRAG_URL,
                username=settings.LIGHTRAG_PUBLIC_USERNAME,
                password=settings.LIGHTRAG_PUBLIC_PASSWORD,
            )
        else:
            _lightrag_clients[kind] = LightRAGClient()
    return _lightrag_clients[kind]


def get_public_lightrag_client() -> LightRAGClient:
    return get_lightrag_client("public")
