from __future__ import annotations

from api.clients.langgraph_client import LangGraphClient


def test_build_messages_uses_langgraph_role_contract() -> None:
    client = LangGraphClient(base_url="https://langgraph.example", assistant_id="retrieval")

    messages = client._build_messages(
        "hoc phi khoa moi nhat",
        [
            {"role": "user", "content": "xin chao"},
            {"type": "ai", "content": "chao ban"},
            {"role": "system", "content": "tra loi ngan gon"},
            {"role": "unknown", "content": "ignored"},
            {"role": "assistant", "content": ""},
        ],
    )

    assert messages == [
        {"role": "user", "content": "xin chao"},
        {"role": "assistant", "content": "chao ban"},
        {"role": "system", "content": "tra loi ngan gon"},
        {"role": "user", "content": "hoc phi khoa moi nhat"},
    ]
    assert all("type" not in message for message in messages)
