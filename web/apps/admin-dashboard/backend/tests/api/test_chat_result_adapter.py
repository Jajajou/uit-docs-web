from __future__ import annotations

from api.services.chat_result_adapter import normalize_chat_result


def test_normalize_chat_result_preserves_langgraph_context_interrupt():
    result = normalize_chat_result(
        {
            "__interrupt__": [
                {
                    "value": {
                        "action": "request_context",
                        "missing_fields": ["khóa học", "hệ đào tạo"],
                        "message": (
                            "Câu hỏi liên quan đến quy chế/quy định sinh viên. "
                            "Vui lòng cung cấp: khóa học (ví dụ: 2022, K22), "
                            "hệ đào tạo (chinh_quy / lien_thong / tu_xa)."
                        ),
                    },
                    "id": "interrupt-001",
                }
            ]
        }
    )

    assert result.response_type == "partial_answer"
    assert result.no_context is False
    assert "Vui lòng cung cấp" in result.response_text
    assert "khóa học" in result.response_text
    assert result.references == []


def test_normalize_chat_result_builds_interrupt_message_from_missing_fields():
    result = normalize_chat_result(
        {
            "__interrupt__": [
                {
                    "value": {
                        "action": "request_context",
                        "missing_fields": ["khóa học", "hệ đào tạo"],
                    },
                    "id": "interrupt-002",
                }
            ]
        }
    )

    assert result.response_type == "partial_answer"
    assert result.no_context is False
    assert result.response_text == "Vui lòng cung cấp thêm thông tin: khóa học, hệ đào tạo."
