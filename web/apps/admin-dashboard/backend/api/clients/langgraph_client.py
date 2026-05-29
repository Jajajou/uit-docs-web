"""LangGraph query client for the admin dashboard backend."""

from __future__ import annotations

from typing import Literal

import requests

from api.config import settings

DEFAULT_TIMEOUT = 180

_ROLE_MAP = {
    "user": "human",
    "assistant": "ai",
    "system": "system",
    "human": "human",
    "ai": "ai",
}


class LangGraphClient:
    """Thin client for LangGraph `/runs/wait` query execution."""

    def __init__(
        self,
        *,
        base_url: str,
        assistant_id: str,
        api_key: str = "",
        timeout_seconds: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.assistant_id = assistant_id.strip()
        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_messages(self, question: str, conversation_history: list[dict] | None = None) -> list[dict]:
        messages: list[dict] = []

        for item in conversation_history or []:
            role = str(item.get("role") or item.get("type") or "").strip().lower()
            content = str(item.get("content") or "").strip()
            mapped_role = _ROLE_MAP.get(role)
            if mapped_role and content:
                messages.append({"type": mapped_role, "content": content})

        messages.append({"type": "human", "content": question})
        return messages

    @staticmethod
    def _unwrap_response(payload: dict | None) -> dict:
        if not isinstance(payload, dict):
            return {}

        for key in ("values", "output", "result"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                return nested

        return payload

    def health(self) -> dict:
        if not self.base_url:
            return {"status": "disabled"}
        try:
            response = self.session.get(f"{self.base_url}/ok", timeout=self.timeout_seconds)
            return {"status": "ok" if response.ok else "unhealthy", "status_code": response.status_code}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def query_text(
        self,
        query: str,
        *,
        conversation_history: list[dict] | None = None,
        **_: object,
    ) -> dict:
        if not self.base_url:
            return {"error": "langgraph_url_not_configured"}
        if not self.assistant_id:
            return {"error": "langgraph_assistant_not_configured"}

        payload = {
            "assistant_id": self.assistant_id,
            "input": {
                "messages": self._build_messages(query, conversation_history),
            },
        }

        try:
            response = self.session.post(
                f"{self.base_url}/runs/wait",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            return {"error": str(exc)}

        if not response.ok:
            return {"error": response.text, "status_code": response.status_code}

        try:
            return self._unwrap_response(response.json())
        except ValueError:
            return {"error": "invalid_langgraph_response"}


_langgraph_clients: dict[str, LangGraphClient] = {}


def get_langgraph_client(kind: Literal["internal", "public"] = "internal") -> LangGraphClient:
    if kind not in _langgraph_clients:
        if kind == "public":
            _langgraph_clients[kind] = LangGraphClient(
                base_url=settings.LANGGRAPH_PUBLIC_URL or settings.LANGGRAPH_URL,
                assistant_id=settings.LANGGRAPH_PUBLIC_ASSISTANT_ID,
                api_key=settings.LANGGRAPH_PUBLIC_API_KEY,
                timeout_seconds=settings.LANGGRAPH_TIMEOUT_SECONDS,
            )
        else:
            _langgraph_clients[kind] = LangGraphClient(
                base_url=settings.LANGGRAPH_URL,
                assistant_id=settings.LANGGRAPH_INTERNAL_ASSISTANT_ID,
                api_key=settings.LANGGRAPH_API_KEY,
                timeout_seconds=settings.LANGGRAPH_TIMEOUT_SECONDS,
            )
    return _langgraph_clients[kind]


def get_internal_langgraph_client() -> LangGraphClient:
    return get_langgraph_client("internal")


def get_public_langgraph_client() -> LangGraphClient:
    return get_langgraph_client("public")
