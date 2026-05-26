from __future__ import annotations

from api.services.chat_result_adapter import normalize_chat_result


def test_normalize_chat_result_accepts_langgraph_retrieved_chunks() -> None:
    normalized = normalize_chat_result(
        {
            "final_answer": "Hoc phi khoa moi nhat la 42.000.000 dong/nam hoc.",
            "retrieved_chunks": [
                {
                    "content": "Hoc phi khoa moi nhat la 42.000.000 dong/nam hoc.",
                    "metadata": {
                        "title": "Thong bao hoc phi 2025-2026",
                        "url": "https://uit.example.edu/hoc-phi-2025.pdf",
                    },
                }
            ],
        }
    )

    assert normalized.response_text.startswith("Hoc phi khoa moi nhat")
    assert normalized.response_type == "full_answer"
    assert normalized.references == [
        {
            "reference_id": "ref-1",
            "content": "Hoc phi khoa moi nhat la 42.000.000 dong/nam hoc.",
            "metadata": {
                "title": "Thong bao hoc phi 2025-2026",
                "url": "https://uit.example.edu/hoc-phi-2025.pdf",
            },
            "title": "Thong bao hoc phi 2025-2026",
            "excerpt": "Hoc phi khoa moi nhat la 42.000.000 dong/nam hoc.",
            "file_path": "https://uit.example.edu/hoc-phi-2025.pdf",
        }
    ]
