from __future__ import annotations

from api.config import settings
from api.dependencies import get_workspace_service
import api.services.workspace_service as workspace_service_module

from .conftest import auth_headers


def test_documents_endpoints_return_expected_envelopes(client):
    list_response = client.get("/api/documents", headers=auth_headers("student", "req-doc-001"))
    detail_response = client.get("/api/documents/doc-004", headers=auth_headers("student", "req-doc-002"))

    assert list_response.status_code == 200
    assert "documents" in list_response.json()
    assert detail_response.status_code == 200
    assert "document" in detail_response.json()
    assert detail_response.json()["document"]["temporal_metadata"]["document_type"] == "announcement"


def test_legacy_upload_alias_remains_available(client):
    response = client.post(
        "/api/upload/url",
        headers=auth_headers("teacher", "req-doc-003"),
        json={
            "sourceType": "url",
            "title": "Thong bao test legacy alias",
            "url": "https://uit.edu.vn/test",
            "issuingUnit": "Phong Dao tao Dai hoc",
            "visibilityScope": "internal",
            "tags": ["legacy"],
            "notes": "Legacy alias test",
        },
    )

    assert response.status_code == 202
    assert response.json()["submission"]["source_type"] == "url"


def test_chat_low_confidence_scenario_returns_warning(client):
    response = client.post(
        "/api/chat/stream?scenario=low-confidence",
        headers=auth_headers("student", "req-chat-001"),
        json={
            "conversationId": "conv-001",
            "message": "Hoc phi hoc ky 2 co gi thay doi?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["confidence"] == 0.35
    assert body["message"]["warnings"][0]["code"] == "low_confidence"
    assert body["message"]["references"][0]["title"] == "Tài liệu đang chờ kiểm duyệt nội bộ"


def test_chat_sessions_start_empty_without_seeded_conversations(client):
    response = client.get("/api/chat/sessions", headers=auth_headers("student", "req-chat-empty-001"))

    assert response.status_code == 200
    assert response.json()["conversations"] == []


def test_chat_sessions_student_redacts_internal_reference_titles(client):
    client.post(
        "/api/chat/stream?scenario=low-confidence",
        headers=auth_headers("student", "req-chat-001b-seed"),
        json={
            "conversationId": "conv-student-001",
            "message": "Hoc phi hoc ky 2 co gi thay doi?",
        },
    )
    response = client.get("/api/chat/sessions", headers=auth_headers("student", "req-chat-001b"))

    assert response.status_code == 200
    references = response.json()["conversations"][0]["messages"][1]["references"]
    assert references[0]["title"] == "Tài liệu đang chờ kiểm duyệt nội bộ"


def test_chat_sessions_admin_keeps_internal_reference_titles(client):
    client.post(
        "/api/chat/stream?scenario=low-confidence",
        headers=auth_headers("admin", "req-chat-001c-seed"),
        json={
            "conversationId": "conv-admin-001",
            "message": "Hoc phi hoc ky 2 co gi thay doi?",
        },
    )
    response = client.get("/api/chat/sessions", headers=auth_headers("admin", "req-chat-001c"))

    assert response.status_code == 200
    references = response.json()["conversations"][0]["messages"][1]["references"]
    assert references[0]["title"] == "Thông báo học phí học kỳ 2"


def test_chat_sessions_are_scoped_per_owner(client):
    client.post(
        "/api/chat/stream",
        headers=auth_headers("student", "req-chat-scope-001"),
        json={
            "conversationId": "conv-student-scope",
            "message": "Lich dang ky mon hoc cua khoa 2024 co thay doi khong?",
        },
    )
    client.post(
        "/api/chat/stream",
        headers=auth_headers("admin", "req-chat-scope-002"),
        json={
            "conversationId": "conv-admin-scope",
            "message": "Tong hop trang thai ingestion hien tai.",
        },
    )

    student_response = client.get("/api/chat/sessions", headers=auth_headers("student", "req-chat-scope-003"))
    admin_response = client.get("/api/chat/sessions", headers=auth_headers("admin", "req-chat-scope-004"))

    assert student_response.status_code == 200
    assert admin_response.status_code == 200
    assert [conversation["id"] for conversation in student_response.json()["conversations"]] == ["conv-student-scope"]
    assert [conversation["id"] for conversation in admin_response.json()["conversations"]] == ["conv-admin-scope"]


def test_chat_delete_and_clear_only_affect_current_owner(client):
    client.post(
        "/api/chat/stream",
        headers=auth_headers("student", "req-chat-delete-001"),
        json={
            "conversationId": "conv-student-delete",
            "message": "Cho toi xem lich su hoc phi cong khai.",
        },
    )
    client.post(
        "/api/chat/stream",
        headers=auth_headers("admin", "req-chat-delete-002"),
        json={
            "conversationId": "conv-admin-keep",
            "message": "Cho toi xem job ingestion gan day.",
        },
    )

    delete_response = client.delete(
        "/api/chat/sessions/conv-student-delete",
        headers=auth_headers("student", "req-chat-delete-003"),
    )
    student_after_delete = client.get("/api/chat/sessions", headers=auth_headers("student", "req-chat-delete-004"))
    admin_after_delete = client.get("/api/chat/sessions", headers=auth_headers("admin", "req-chat-delete-005"))

    assert delete_response.status_code == 204
    assert student_after_delete.json()["conversations"] == []
    assert [conversation["id"] for conversation in admin_after_delete.json()["conversations"]] == ["conv-admin-keep"]

    second_student = client.post(
        "/api/chat/stream",
        headers=auth_headers("student", "req-chat-delete-006"),
        json={
            "conversationId": "conv-student-clear",
            "message": "Cho toi xem hoc bong cong khai.",
        },
    )
    assert second_student.status_code == 200

    clear_response = client.delete("/api/chat/sessions", headers=auth_headers("student", "req-chat-delete-007"))
    student_after_clear = client.get("/api/chat/sessions", headers=auth_headers("student", "req-chat-delete-008"))
    admin_after_clear = client.get("/api/chat/sessions", headers=auth_headers("admin", "req-chat-delete-009"))

    assert clear_response.status_code == 204
    assert student_after_clear.json()["conversations"] == []
    assert [conversation["id"] for conversation in admin_after_clear.json()["conversations"]] == ["conv-admin-keep"]


def test_legacy_role_owned_conversation_is_visible_and_deletable_after_session_owner_upgrade():
    service = get_workspace_service()
    service.store.upsert_conversation(
        {
            "id": "conv-legacy-student",
            "owner_key": "role:student",
            "title": "Cuộc trò chuyện cũ",
            "updated_at": "2026-04-13T10:00:00Z",
            "messages": [],
        }
    )
    session = {
        "session_id": "session-live-001",
        "user": {
            "email": "22520807@gm.uit.edu.vn",
        },
    }

    conversations = service.list_conversations("happy", "student", session, None)

    assert [conversation["id"] for conversation in conversations] == ["conv-legacy-student"]
    assert service.store.get_conversation_by_id("conv-legacy-student")["owner_key"] == "user:22520807@gm.uit.edu.vn"

    service.delete_conversation("conv-legacy-student", "student", session, None)

    assert service.store.get_conversation_by_id("conv-legacy-student") is None


def test_chat_stream_uses_live_lightrag_for_admin_when_enabled(client, monkeypatch):
    class FakeLightRAGClient:
        def query_text(self, query, **kwargs):
            assert query == "Hoc phi hoc ky 1 nam hoc 2024-2025 nhu the nao?"
            assert kwargs["include_chunk_content"] is True
            return {
                "response": "Hoc phi duoc tinh theo thong bao hoc phi da duoc duyet.",
                "references": [
                    {
                        "reference_id": "ref-live-001",
                        "file_path": "/uploads/quy-dinh-hoc-vu-2024-2025.pdf",
                    }
                ],
            }

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(workspace_service_module, "get_lightrag_client", lambda: FakeLightRAGClient())

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("admin", "req-chat-live-001"),
        json={
            "message": "Hoc phi hoc ky 1 nam hoc 2024-2025 nhu the nao?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["content"] == "Hoc phi duoc tinh theo thong bao hoc phi da duoc duyet."
    assert body["message"]["confidence"] == 0.82
    assert body["message"]["references"][0]["href"].startswith("/documents/")
    assert body["message"]["warnings"] == []


def test_chat_stream_strips_markdown_bold_markers_from_live_answer(client, monkeypatch):
    class MarkdownLightRAGClient:
        def query_text(self, query, **kwargs):
            assert query == "Lich dang ky mon hoc cua khoa 2024 co thay doi khong?"
            assert kwargs["include_chunk_content"] is True
            return {
                "response": (
                    "Lich dang ky cua khoa 2024 **khong bi thay doi** theo **Thong Bao Lich Dang Ky Mon Hoc** "
                    "va co hieu luc tu **2026-03-20 den 2026-04-05**."
                ),
                "references": [
                    {
                        "reference_id": "ref-live-001-markdown",
                        "file_path": "/uploads/thong-bao-lich-dang-ky-mon-hoc.pdf",
                    }
                ],
            }

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(workspace_service_module, "get_lightrag_client", lambda: MarkdownLightRAGClient())

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("admin", "req-chat-live-001-markdown"),
        json={
            "message": "Lich dang ky mon hoc cua khoa 2024 co thay doi khong?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "**" not in body["message"]["content"]
    assert "khong bi thay doi" in body["message"]["content"]
    assert "Thong Bao Lich Dang Ky Mon Hoc" in body["message"]["content"]


def test_chat_stream_maps_partial_response_type_and_legacy_file_source_for_admin(client, monkeypatch):
    class PartialAnswerLightRAGClient:
        def query_text(self, query, **kwargs):
            assert query == "Hoc phi hoc ky 1 nam hoc 2024-2025 nhu the nao?"
            assert kwargs["include_chunk_content"] is True
            return {
                "final_answer": "Hoc phi duoc tinh theo thong bao da duoc duyet, nhung can doi chieu them muc chi tiet.",
                "response_type": "partial_answer",
                "references": [
                    {
                        "reference_id": "ref-live-001b",
                        "file_source": "/uploads/quy-dinh-hoc-vu-2024-2025.pdf",
                    }
                ],
            }

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(workspace_service_module, "get_lightrag_client", lambda: PartialAnswerLightRAGClient())

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("admin", "req-chat-live-001b"),
        json={
            "message": "Hoc phi hoc ky 1 nam hoc 2024-2025 nhu the nao?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["content"] == "Hoc phi duoc tinh theo thong bao da duoc duyet, nhung can doi chieu them muc chi tiet."
    assert body["message"]["confidence"] == 0.66
    assert body["message"]["references"][0]["href"] == "/documents/doc-001"
    assert body["message"]["warnings"][0]["code"] == "partial_answer"


def test_chat_stream_refuses_strong_conclusion_when_live_sources_are_only_indirectly_related(client, monkeypatch):
    class WeakGroundingLightRAGClient:
        def query_text(self, query, **kwargs):
            assert query == "Thong bao hoc phi hien tai con hieu luc khong?"
            assert kwargs["include_chunk_content"] is True
            return {
                "response": "Thong bao hoc phi hien tai khong con hieu luc va nen doi chieu voi quy dinh hoc vu 2024-2025.",
                "references": [
                    {
                        "reference_id": "ref-live-weak-001",
                        "file_path": "/uploads/quy-dinh-hoc-vu-2024-2025.pdf",
                    }
                ],
            }

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(workspace_service_module, "get_lightrag_client", lambda: WeakGroundingLightRAGClient())

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("admin", "req-chat-live-weak-001"),
        json={
            "message": "Thong bao hoc phi hien tai con hieu luc khong?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "chua co du can cu" in workspace_service_module.normalize_search_text(body["message"]["content"])
    assert body["message"]["warnings"][0]["code"] == "insufficient_grounding"
    assert body["message"]["confidence"] == 0.38
    assert body["message"]["references"][0]["href"] == "/documents/doc-001"


def test_chat_stream_uses_public_catalog_path_for_student_even_when_live_enabled(client, monkeypatch):
    class FakePublicLightRAGClient:
        def __init__(self):
            self.inserted_sources: list[str] = []

        def find_document_ids_by_file_path(self, file_path):
            return []

        def delete_document(self, doc_ids):
            return {"status": "deleted"}

        def insert_text(self, text, source=None):
            self.inserted_sources.append(source)
            return {"status": "success", "track_id": "public-seed-track"}

        def query_text(self, query, **kwargs):
            assert "Câu hỏi: Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?" in query
            assert "Phân biệt rõ giữa khóa tuyển sinh và năm học." in query
            return {
                "response": "Lich dang ky mon hoc khoa 2024 da duoc cong bo trong thong bao cong khai cua UIT.",
                "references": [
                    {
                        "reference_id": "ref-public-live-001",
                        "file_path": "admin-dashboard-public://doc-004",
                    }
                ],
            }

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(settings, "LIGHTRAG_PUBLIC_URL", "http://127.0.0.1:9623")
    public_client = FakePublicLightRAGClient()
    monkeypatch.setattr(workspace_service_module, "get_public_lightrag_client", lambda: public_client)

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("student", "req-chat-live-002"),
        json={
            "message": "Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "Theo các tài liệu công khai UIT đang được trích dẫn về lịch đăng ký môn học:" in body["message"]["content"]
    assert "Thông báo lịch đăng ký môn học" in body["message"]["content"]
    assert "Mở mục \"Nguồn tài liệu\"" in body["message"]["content"]
    assert body["message"]["references"][0]["href"] == "/documents/doc-004"
    assert body["message"]["warnings"] == []
    assert "admin-dashboard-public://doc-004" in public_client.inserted_sources


def test_chat_stream_maps_partial_response_type_and_legacy_file_source_for_student(client, monkeypatch):
    class PartialAnswerPublicLightRAGClient:
        def __init__(self):
            self.inserted_sources: list[str] = []

        def find_document_ids_by_file_path(self, file_path):
            return []

        def delete_document(self, doc_ids):
            return {"status": "deleted"}

        def insert_text(self, text, source=None):
            self.inserted_sources.append(source)
            return {"status": "success", "track_id": "public-seed-track"}

        def query_text(self, query, **kwargs):
            return {
                "generated_response": "Co mot phan thong tin da duoc xac nhan trong tai lieu cong khai.",
                "response_type": "partial_answer",
                "references": [
                    {
                        "reference_id": "ref-public-live-001b",
                        "file_source": "admin-dashboard-public://doc-004",
                    }
                ],
            }

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(settings, "LIGHTRAG_PUBLIC_URL", "http://127.0.0.1:9623")
    public_client = PartialAnswerPublicLightRAGClient()
    monkeypatch.setattr(workspace_service_module, "get_public_lightrag_client", lambda: public_client)

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("student", "req-chat-live-002e"),
        json={
            "message": "Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["references"][0]["href"] == "/documents/doc-004"
    assert body["message"]["confidence"] == 0.56
    assert body["message"]["warnings"][0]["code"] == "partial_answer"
    assert "Thông báo lịch đăng ký môn học" in body["message"]["content"]


def test_public_workspace_document_text_uses_seed_excerpt_and_clean_vietnamese():
    service = get_workspace_service()
    document = service.store.get_document_by_id("doc-004")

    assert document is not None

    text = service._build_public_workspace_document_text(document)

    assert "Trích yếu nội dung:" in text
    assert "Thông báo lịch đăng ký môn học áp dụng trực tiếp cho sinh viên khóa tuyển sinh 2024, 2025 và 2026." in text
    assert "Thời gian đăng ký từ ngày 20/03/2026 đến ngày 05/04/2026." in text
    assert "Đơn vị ban hành: Phòng Đào tạo Đại học" in text
    assert "Khóa tuyển sinh liên quan: 2024, 2025, 2026" in text


def test_chat_live_sync_persists_langgraph_result_for_student(client):
    response = client.post(
        "/api/chat/live-sync",
        headers=auth_headers("student", "req-chat-live-sync-001"),
        json={
            "conversationId": "conv-live-sync-student",
            "message": "Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?",
            "result": {
                "generated_response": "Co mot phan thong tin da duoc xac nhan trong tai lieu cong khai.",
                "response_type": "partial_answer",
                "references": [
                    {
                        "reference_id": "ref-public-live-sync-001",
                        "file_source": "admin-dashboard-public://doc-004",
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == "conv-live-sync-student"
    assert body["message"]["references"][0]["href"] == "/documents/doc-004"
    assert body["message"]["warnings"][0]["code"] == "partial_answer"
    assert body["message"]["content"] == "Co mot phan thong tin da duoc xac nhan trong tai lieu cong khai."

    sessions = client.get("/api/chat/sessions", headers=auth_headers("student", "req-chat-live-sync-002"))

    assert sessions.status_code == 200
    assert sessions.json()["conversations"][0]["id"] == "conv-live-sync-student"


def test_chat_live_sync_keeps_langgraph_answer_when_public_grounding_is_weak(client):
    response = client.post(
        "/api/chat/live-sync",
        headers=auth_headers("student", "req-chat-live-sync-003"),
        json={
            "conversationId": "conv-live-sync-weak-grounding",
            "message": "Hoc phi khoa moi nhat la bao nhieu?",
            "result": {
                "final_answer": (
                    "Hoc phi ap dung cho khoa sinh vien moi nhat la 42.000.000 dong/nam hoc, "
                    "ap dung cho sinh vien chinh quy nam hoc 2025-2026."
                ),
                "response_type": "full_answer",
                "references": [
                    {
                        "reference_id": "ref-public-live-sync-weak-001",
                        "file_source": "admin-dashboard-public://doc-004",
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "42.000.000 dong/nam hoc" in body["message"]["content"]
    assert "hien toi moi tim thay" not in workspace_service_module.normalize_search_text(body["message"]["content"])
    assert body["message"]["references"][0]["href"] == "/documents/doc-004"


def test_chat_live_sync_keeps_langgraph_answer_without_references(client):
    response = client.post(
        "/api/chat/live-sync",
        headers=auth_headers("student", "req-chat-live-sync-004"),
        json={
            "conversationId": "conv-live-sync-no-refs",
            "message": "Hoc phi khoa moi nhat la bao nhieu?",
            "result": {
                "final_answer": (
                    "Hoc phi ap dung cho khoa sinh vien moi nhat la 42.000.000 dong/nam hoc.\n\n"
                    "Tai lieu tham khao\n- Thong bao hoc phi"
                ),
                "response_type": "full_answer",
                "references": [],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["content"] == "Hoc phi ap dung cho khoa sinh vien moi nhat la 42.000.000 dong/nam hoc."
    assert body["message"]["references"] == []
    assert body["message"]["warnings"][-1]["code"] == "insufficient_grounding"


def test_chat_live_sync_extracts_markdown_references_when_live_payload_has_no_structured_sources(client):
    response = client.post(
        "/api/chat/live-sync",
        headers=auth_headers("student", "req-chat-live-sync-005"),
        json={
            "conversationId": "conv-live-sync-markdown-refs",
            "message": "Hoc phi hoc ky 1 nam hoc 2024-2025 nhu the nao?",
            "result": {
                "final_answer": (
                    "Hoc phi hoc ky 1 nam hoc 2024-2025 duoc tinh theo so tin chi dang ky.\n\n"
                    "## Tai lieu tham khao\n"
                    "- [Quy dinh hoc vu 2024-2025](/uploads/quy-dinh-hoc-vu-2024-2025.pdf)\n"
                    "- [Thong bao dang ky mon hoc](https://daa.uit.edu.vn/sites/daa/files/202603/thong_bao_lich_dang_ky_mon_hoc_2026.pdf)"
                ),
                "response_type": "partial_answer",
                "references": [],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["content"] == "Hoc phi hoc ky 1 nam hoc 2024-2025 duoc tinh theo so tin chi dang ky."
    assert body["message"]["references"][0]["href"].startswith("/documents/doc-")
    assert body["message"]["references"][1]["href"] == "https://daa.uit.edu.vn/sites/daa/files/202603/thong_bao_lich_dang_ky_mon_hoc_2026.pdf"
    assert body["message"]["references"][1]["title"] == "Thong bao dang ky mon hoc"
    assert body["message"]["warnings"][0]["code"] == "partial_answer"


def test_chat_stream_falls_back_to_public_catalog_when_public_live_query_fails(client, monkeypatch):
    class FailingPublicLightRAGClient:
        def find_document_ids_by_file_path(self, file_path):
            return []

        def delete_document(self, doc_ids):
            return {"status": "deleted"}

        def insert_text(self, text, source=None):
            return {"status": "success", "track_id": "public-seed-track"}

        def query_text(self, query, **kwargs):
            return {"error": "public workspace unavailable"}

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(settings, "LIGHTRAG_PUBLIC_URL", "http://127.0.0.1:9623")
    monkeypatch.setattr(workspace_service_module, "get_public_lightrag_client", lambda: FailingPublicLightRAGClient())

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("student", "req-chat-live-002b"),
        json={
            "message": "Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "Thông báo lịch đăng ký môn học" in body["message"]["content"]
    assert body["message"]["references"][0]["href"] == "/documents/doc-004"


def test_chat_stream_reseeds_failed_public_documents_before_live_query(client, monkeypatch):
    class RecoveringPublicLightRAGClient:
        def __init__(self):
            self.inserted_sources: list[str] = []
            self.deleted_doc_ids: list[str] = []
            self.poll_counts: dict[str, int] = {}
            self.documents_by_source = {
                "admin-dashboard-public://doc-001": [{"id": "failed-doc-001", "status": "failed"}],
                "admin-dashboard-public://doc-004": [{"id": "failed-doc-004", "status": "failed"}],
            }

        def find_documents_by_file_path(self, file_path):
            documents = [dict(document) for document in self.documents_by_source.get(file_path, [])]
            if documents and documents[0]["status"] == "processing":
                self.poll_counts[file_path] = self.poll_counts.get(file_path, 0) + 1
                if self.poll_counts[file_path] >= 2:
                    documents = [{"id": documents[0]["id"], "status": "processed"}]
                    self.documents_by_source[file_path] = [dict(documents[0])]
            return documents

        def find_document_ids_by_file_path(self, file_path):
            return [document["id"] for document in self.find_documents_by_file_path(file_path)]

        def delete_document(self, doc_ids):
            self.deleted_doc_ids.extend(doc_ids)
            for file_path, documents in list(self.documents_by_source.items()):
                self.documents_by_source[file_path] = [
                    document for document in documents if document["id"] not in doc_ids
                ]
            return {"status": "deleted"}

        def insert_text(self, text, source=None):
            assert source is not None
            self.inserted_sources.append(source)
            self.documents_by_source[source] = [
                {"id": f"processed-{source.rsplit('://', 1)[-1]}", "status": "processing"}
            ]
            return {"status": "success", "track_id": f"track-{len(self.inserted_sources)}"}

        def query_text(self, query, **kwargs):
            assert "Câu hỏi: Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?" in query
            assert "Phân biệt rõ giữa khóa tuyển sinh và năm học." in query
            return {
                "response": "Lich dang ky mon hoc khoa 2024 da duoc cong bo trong thong bao cong khai cua UIT.",
                "references": [
                    {
                        "reference_id": "ref-public-live-002",
                        "file_path": "admin-dashboard-public://doc-004",
                    }
                ],
            }

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(settings, "LIGHTRAG_PUBLIC_URL", "http://127.0.0.1:9623")
    monkeypatch.setattr(workspace_service_module, "sleep", lambda _: None)
    public_client = RecoveringPublicLightRAGClient()
    monkeypatch.setattr(workspace_service_module, "get_public_lightrag_client", lambda: public_client)

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("student", "req-chat-live-002c"),
        json={
            "message": "Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "Theo các tài liệu công khai UIT đang được trích dẫn về lịch đăng ký môn học:" in body["message"]["content"]
    assert "Thông báo lịch đăng ký môn học" in body["message"]["content"]
    assert body["message"]["references"][0]["href"] == "/documents/doc-004"
    assert body["message"]["warnings"] == []
    assert set(public_client.deleted_doc_ids) == {"failed-doc-001", "failed-doc-004"}
    assert {
        "admin-dashboard-public://doc-001",
        "admin-dashboard-public://doc-004",
    }.issubset(set(public_client.inserted_sources))


def test_chat_stream_forces_public_reseed_when_live_query_returns_no_context(client, monkeypatch):
    class EmptyThenReadyPublicLightRAGClient:
        def __init__(self):
            self.inserted_sources: list[str] = []
            self.query_count = 0
            self.documents_by_source = {
                "admin-dashboard-public://doc-001": [{"id": "processed-doc-001", "status": "processed"}],
                "admin-dashboard-public://doc-004": [{"id": "processed-doc-004", "status": "processed"}],
            }

        def find_documents_by_file_path(self, file_path):
            return [dict(document) for document in self.documents_by_source.get(file_path, [])]

        def find_document_ids_by_file_path(self, file_path):
            return [document["id"] for document in self.find_documents_by_file_path(file_path)]

        def delete_document(self, doc_ids):
            for file_path, documents in list(self.documents_by_source.items()):
                self.documents_by_source[file_path] = [
                    document for document in documents if document["id"] not in doc_ids
                ]
            return {"status": "deleted"}

        def insert_text(self, text, source=None):
            assert source is not None
            self.inserted_sources.append(source)
            self.documents_by_source[source] = [{"id": f"reseeded-{source.rsplit('://', 1)[-1]}", "status": "processed"}]
            return {"status": "success", "track_id": f"track-{len(self.inserted_sources)}"}

        def query_text(self, query, **kwargs):
            self.query_count += 1
            if self.query_count == 1:
                return {"response": "No relevant context found.", "references": []}
            return {
                "response": "Thong bao cong khai xac nhan lich dang ky mon hoc khoa 2024 tu 2026-03-20 den 2026-04-05.",
                "references": [
                    {
                        "reference_id": "ref-public-live-003",
                        "file_path": "admin-dashboard-public://doc-004",
                    }
                ],
            }

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(settings, "LIGHTRAG_PUBLIC_URL", "http://127.0.0.1:9623")
    monkeypatch.setattr(workspace_service_module, "sleep", lambda _: None)
    public_client = EmptyThenReadyPublicLightRAGClient()
    monkeypatch.setattr(workspace_service_module, "get_public_lightrag_client", lambda: public_client)

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("student", "req-chat-live-002d"),
        json={
            "message": "Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "2026-03-20" in body["message"]["content"]
    assert "Mở mục \"Nguồn tài liệu\"" in body["message"]["content"]
    assert body["message"]["references"][0]["href"] == "/documents/doc-004"
    assert public_client.query_count == 2
    assert {
        "admin-dashboard-public://doc-001",
        "admin-dashboard-public://doc-004",
    }.issubset(set(public_client.inserted_sources))


def test_chat_stream_falls_back_to_contract_reply_when_live_lightrag_fails(client, monkeypatch):
    class FailingLightRAGClient:
        def query_text(self, query, **kwargs):
            return {"error": "downstream timeout"}

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(workspace_service_module, "get_lightrag_client", lambda: FailingLightRAGClient())

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("admin", "req-chat-live-003"),
        json={
            "message": "Hoc phi hoc ky 1 nam hoc 2024-2025 nhu the nao?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["confidence"] == 0.24
    assert body["message"]["references"][0]["href"] == "/documents/doc-001"
    assert body["message"]["warnings"][-1]["code"] == "live_backend_unavailable"
    assert "phan hoi du phong" in workspace_service_module.normalize_search_text(body["message"]["content"])


def test_chat_stream_forces_internal_reseed_when_live_query_returns_no_context(client, monkeypatch):
    class EmptyThenReadyLightRAGClient:
        def __init__(self):
            self.inserted_sources: list[str] = []
            self.query_count = 0
            self.documents_by_source = {
                "admin-dashboard-live://doc-001": [{"id": "processed-doc-001", "status": "processed"}],
                "admin-dashboard-live://doc-004": [{"id": "processed-doc-004", "status": "processed"}],
            }

        def find_documents_by_file_path(self, file_path):
            return [dict(document) for document in self.documents_by_source.get(file_path, [])]

        def find_document_ids_by_file_path(self, file_path):
            return [document["id"] for document in self.find_documents_by_file_path(file_path)]

        def delete_document(self, doc_ids):
            for file_path, documents in list(self.documents_by_source.items()):
                self.documents_by_source[file_path] = [
                    document for document in documents if document["id"] not in doc_ids
                ]
            return {"status": "deleted"}

        def insert_text(self, text, source=None):
            assert source is not None
            self.inserted_sources.append(source)
            self.documents_by_source[source] = [{"id": f"reseeded-{source.rsplit('://', 1)[-1]}", "status": "processed"}]
            return {"status": "success", "track_id": f"track-{len(self.inserted_sources)}"}

        def query_text(self, query, **kwargs):
            self.query_count += 1
            if self.query_count == 1:
                return {"response": "No relevant context found.", "references": []}
            return {
                "response": "Hoc phi duoc tinh theo thong bao hoc phi da duoc duyet.",
                "references": [
                    {
                        "reference_id": "ref-live-004",
                        "file_path": "admin-dashboard-live://doc-001",
                    }
                ],
            }

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(workspace_service_module, "sleep", lambda _: None)
    live_client = EmptyThenReadyLightRAGClient()
    monkeypatch.setattr(workspace_service_module, "get_lightrag_client", lambda: live_client)

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("admin", "req-chat-live-004"),
        json={
            "message": "Hoc phi hoc ky 1 nam hoc 2024-2025 nhu the nao?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "Hoc phi duoc tinh" in body["message"]["content"]
    assert body["message"]["references"][0]["href"] == "/documents/doc-001"
    assert live_client.query_count == 2
    assert {
        "admin-dashboard-live://doc-001",
        "admin-dashboard-live://doc-004",
    }.issubset(set(live_client.inserted_sources))


def test_analytics_endpoints_are_available(client):
    overview = client.get("/api/analytics/overview", headers=auth_headers("admin", "req-chat-002"))
    pipeline = client.get("/api/analytics/pipeline", headers=auth_headers("admin", "req-chat-003"))
    health = client.get("/api/analytics/health", headers=auth_headers("admin", "req-chat-004"))

    assert overview.status_code == 200
    assert overview.json()["total_documents"] >= 1
    assert pipeline.status_code == 200
    assert "queue_size" in pipeline.json()
    assert health.status_code == 200
    assert health.json()["admin_api"] == "healthy"


def test_analytics_health_reflects_live_lightrag_when_enabled(client, monkeypatch):
    class FakeLightRAGClient:
        def health(self):
            return {"status": "healthy", "url": "http://127.0.0.1:9622"}

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(workspace_service_module, "get_lightrag_client", lambda: FakeLightRAGClient())

    overview = client.get("/api/analytics/overview", headers=auth_headers("admin", "req-chat-live-004"))
    health = client.get("/api/analytics/health", headers=auth_headers("admin", "req-chat-live-005"))

    assert overview.status_code == 200
    assert overview.json()["lightrag_health"] == "healthy"
    assert health.status_code == 200
    assert health.json()["lightrag"] == "healthy"
    assert health.json()["lightrag_url"] == "http://127.0.0.1:9622"


def test_chat_stream_uses_public_catalog_path_for_student_even_when_live_enabled(client, monkeypatch):
    class FakePublicLightRAGClient:
        def __init__(self):
            self.inserted_sources: list[str] = []

        def find_document_ids_by_file_path(self, file_path):
            return []

        def delete_document(self, doc_ids):
            return {"status": "deleted"}

        def insert_text(self, text, source=None):
            self.inserted_sources.append(source)
            return {"status": "success", "track_id": "public-seed-track"}

        def query_text(self, query, **kwargs):
            assert query == "Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?"
            assert kwargs["include_chunk_content"] is True
            return {
                "response": "Lich dang ky mon hoc khoa 2024 da duoc cong bo trong thong bao cong khai cua UIT.",
                "references": [
                    {
                        "reference_id": "ref-public-live-001",
                        "file_path": "admin-dashboard-public://doc-004",
                    }
                ],
            }

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(settings, "LIGHTRAG_PUBLIC_URL", "http://127.0.0.1:9623")
    public_client = FakePublicLightRAGClient()
    monkeypatch.setattr(workspace_service_module, "get_public_lightrag_client", lambda: public_client)

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("student", "req-chat-live-002"),
        json={
            "message": "Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["content"] == "Lich dang ky mon hoc khoa 2024 da duoc cong bo trong thong bao cong khai cua UIT."
    assert body["message"]["references"][0]["href"] == "/documents/doc-004"
    assert body["message"]["warnings"] == []
    assert "admin-dashboard-public://doc-004" in public_client.inserted_sources


def test_chat_stream_maps_partial_response_type_and_legacy_file_source_for_student(client, monkeypatch):
    class PartialAnswerPublicLightRAGClient:
        def __init__(self):
            self.inserted_sources: list[str] = []

        def find_document_ids_by_file_path(self, file_path):
            return []

        def delete_document(self, doc_ids):
            return {"status": "deleted"}

        def insert_text(self, text, source=None):
            self.inserted_sources.append(source)
            return {"status": "success", "track_id": "public-seed-track"}

        def query_text(self, query, **kwargs):
            assert query == "Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?"
            assert kwargs["include_chunk_content"] is True
            return {
                "generated_response": "Co mot phan thong tin da duoc xac nhan trong tai lieu cong khai.",
                "response_type": "partial_answer",
                "references": [
                    {
                        "reference_id": "ref-public-live-001b",
                        "file_source": "admin-dashboard-public://doc-004",
                    }
                ],
            }

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(settings, "LIGHTRAG_PUBLIC_URL", "http://127.0.0.1:9623")
    public_client = PartialAnswerPublicLightRAGClient()
    monkeypatch.setattr(workspace_service_module, "get_public_lightrag_client", lambda: public_client)

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("student", "req-chat-live-002e"),
        json={
            "message": "Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["references"][0]["href"] == "/documents/doc-004"
    assert body["message"]["confidence"] == 0.56
    assert body["message"]["warnings"][0]["code"] == "partial_answer"
    assert body["message"]["content"] == "Co mot phan thong tin da duoc xac nhan trong tai lieu cong khai."


def test_chat_stream_reseeds_failed_public_documents_before_live_query(client, monkeypatch):
    class RecoveringPublicLightRAGClient:
        def __init__(self):
            self.inserted_sources: list[str] = []
            self.deleted_doc_ids: list[str] = []
            self.poll_counts: dict[str, int] = {}
            self.documents_by_source = {
                "admin-dashboard-public://doc-001": [{"id": "failed-doc-001", "status": "failed"}],
                "admin-dashboard-public://doc-004": [{"id": "failed-doc-004", "status": "failed"}],
            }

        def find_documents_by_file_path(self, file_path):
            documents = [dict(document) for document in self.documents_by_source.get(file_path, [])]
            if documents and documents[0]["status"] == "processing":
                self.poll_counts[file_path] = self.poll_counts.get(file_path, 0) + 1
                if self.poll_counts[file_path] >= 2:
                    documents = [{"id": documents[0]["id"], "status": "processed"}]
                    self.documents_by_source[file_path] = [dict(documents[0])]
            return documents

        def find_document_ids_by_file_path(self, file_path):
            return [document["id"] for document in self.find_documents_by_file_path(file_path)]

        def delete_document(self, doc_ids):
            self.deleted_doc_ids.extend(doc_ids)
            for file_path, documents in list(self.documents_by_source.items()):
                self.documents_by_source[file_path] = [
                    document for document in documents if document["id"] not in doc_ids
                ]
            return {"status": "deleted"}

        def insert_text(self, text, source=None):
            assert source is not None
            self.inserted_sources.append(source)
            self.documents_by_source[source] = [
                {"id": f"processed-{source.rsplit('://', 1)[-1]}", "status": "processing"}
            ]
            return {"status": "success", "track_id": f"track-{len(self.inserted_sources)}"}

        def query_text(self, query, **kwargs):
            assert query == "Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?"
            assert kwargs["include_chunk_content"] is True
            return {
                "response": "Lich dang ky mon hoc khoa 2024 da duoc cong bo trong thong bao cong khai cua UIT.",
                "references": [
                    {
                        "reference_id": "ref-public-live-002",
                        "file_path": "admin-dashboard-public://doc-004",
                    }
                ],
            }

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(settings, "LIGHTRAG_PUBLIC_URL", "http://127.0.0.1:9623")
    monkeypatch.setattr(workspace_service_module, "sleep", lambda _: None)
    public_client = RecoveringPublicLightRAGClient()
    monkeypatch.setattr(workspace_service_module, "get_public_lightrag_client", lambda: public_client)

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("student", "req-chat-live-002c"),
        json={
            "message": "Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["content"] == "Lich dang ky mon hoc khoa 2024 da duoc cong bo trong thong bao cong khai cua UIT."
    assert body["message"]["references"][0]["href"] == "/documents/doc-004"
    assert body["message"]["warnings"] == []
    assert set(public_client.deleted_doc_ids) == {"failed-doc-001", "failed-doc-004"}
    assert {
        "admin-dashboard-public://doc-001",
        "admin-dashboard-public://doc-004",
    }.issubset(set(public_client.inserted_sources))


def test_chat_stream_forces_public_reseed_when_live_query_returns_no_context(client, monkeypatch):
    class EmptyThenReadyPublicLightRAGClient:
        def __init__(self):
            self.inserted_sources: list[str] = []
            self.query_count = 0
            self.documents_by_source = {
                "admin-dashboard-public://doc-001": [{"id": "processed-doc-001", "status": "processed"}],
                "admin-dashboard-public://doc-004": [{"id": "processed-doc-004", "status": "processed"}],
            }

        def find_documents_by_file_path(self, file_path):
            return [dict(document) for document in self.documents_by_source.get(file_path, [])]

        def find_document_ids_by_file_path(self, file_path):
            return [document["id"] for document in self.find_documents_by_file_path(file_path)]

        def delete_document(self, doc_ids):
            for file_path, documents in list(self.documents_by_source.items()):
                self.documents_by_source[file_path] = [
                    document for document in documents if document["id"] not in doc_ids
                ]
            return {"status": "deleted"}

        def insert_text(self, text, source=None):
            assert source is not None
            self.inserted_sources.append(source)
            self.documents_by_source[source] = [{"id": f"reseeded-{source.rsplit('://', 1)[-1]}", "status": "processed"}]
            return {"status": "success", "track_id": f"track-{len(self.inserted_sources)}"}

        def query_text(self, query, **kwargs):
            assert query == "Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?"
            assert kwargs["include_chunk_content"] is True
            self.query_count += 1
            if self.query_count == 1:
                return {"response": "No relevant context found.", "references": []}
            return {
                "response": "Thong bao cong khai xac nhan lich dang ky mon hoc khoa 2024 tu 2026-03-20 den 2026-04-05.",
                "references": [
                    {
                        "reference_id": "ref-public-live-003",
                        "file_path": "admin-dashboard-public://doc-004",
                    }
                ],
            }

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(settings, "LIGHTRAG_PUBLIC_URL", "http://127.0.0.1:9623")
    monkeypatch.setattr(workspace_service_module, "sleep", lambda _: None)
    public_client = EmptyThenReadyPublicLightRAGClient()
    monkeypatch.setattr(workspace_service_module, "get_public_lightrag_client", lambda: public_client)

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("student", "req-chat-live-002d"),
        json={
            "message": "Lich dang ky mon hoc cua khoa 2024 bat dau khi nao?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "2026-03-20" in body["message"]["content"]
    assert body["message"]["references"][0]["href"] == "/documents/doc-004"
    assert public_client.query_count == 2
    assert {
        "admin-dashboard-public://doc-001",
        "admin-dashboard-public://doc-004",
    }.issubset(set(public_client.inserted_sources))


def test_chat_stream_returns_low_grounding_warning_for_student_when_public_live_sources_are_indirect(client, monkeypatch):
    class WeakGroundingPublicLightRAGClient:
        def __init__(self):
            self.inserted_sources: list[str] = []

        def find_document_ids_by_file_path(self, file_path):
            return []

        def delete_document(self, doc_ids):
            return {"status": "deleted"}

        def insert_text(self, text, source=None):
            self.inserted_sources.append(source)
            return {"status": "success", "track_id": "public-seed-track"}

        def query_text(self, query, **kwargs):
            assert query == "Thong bao hoc phi hien tai con hieu luc khong?"
            assert kwargs["include_chunk_content"] is True
            return {
                "response": "Thong bao hoc phi hien tai khong con hieu luc va nen doi chieu voi quy dinh hoc vu 2024-2025.",
                "references": [
                    {
                        "reference_id": "ref-public-live-weak-001",
                        "file_path": "admin-dashboard-public://doc-001",
                    }
                ],
            }

    monkeypatch.setattr(settings, "LIVE_INGESTION_MODE", True)
    monkeypatch.setattr(settings, "LIGHTRAG_PUBLIC_URL", "http://127.0.0.1:9623")
    public_client = WeakGroundingPublicLightRAGClient()
    monkeypatch.setattr(workspace_service_module, "get_public_lightrag_client", lambda: public_client)

    response = client.post(
        "/api/chat/stream",
        headers=auth_headers("student", "req-chat-live-002f"),
        json={
            "message": "Thong bao hoc phi hien tai con hieu luc khong?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "chua co du can cu" in workspace_service_module.normalize_search_text(body["message"]["content"])
    assert body["message"]["warnings"][0]["code"] == "insufficient_grounding"
    assert body["message"]["confidence"] == 0.32
    assert body["message"]["references"][0]["href"] == "/documents/doc-001"
