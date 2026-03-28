from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.dependencies import SERVICE
from api.main import app


@pytest.fixture(autouse=True)
def reset_service_state():
    SERVICE.reset()
    yield
    SERVICE.reset()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(role: str | None = "guest", request_id: str = "test-request-id") -> dict[str, str]:
    headers = {
        "x-request-id": request_id,
    }
    if role is not None:
        headers["x-demo-role"] = role
    return headers


def api_headers(role: str | None = "guest", request_id: str = "test-request-id") -> dict[str, str]:
    return auth_headers(role, request_id)
