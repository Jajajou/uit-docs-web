"""Seed data aligned with the frontend contracts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

MOJIBAKE_MARKERS = ("Ã", "Ä", "Æ", "á»", "áº", "â€", "â€™", "â€“", "â€”")

EXACT_TEXT_REPLACEMENTS = {
    "Nguyen Thi Student": "Nguyễn Thị Student",
    "Guest User": "Người dùng khách",
    "Le Thi Operator": "Lê Thị Operator",
    "Pham Van Lecturer": "Phạm Văn Lecturer",
    "Tran Van Admin": "Trần Văn Admin",
    "Phong Dao tao": "Phòng Đào tạo",
    "Phong Dao tao Dai hoc": "Phòng Đào tạo Đại học",
    "Phòng Đào tạo Dai hoc": "Phòng Đào tạo Đại học",
    "Phong Cong tac Sinh vien": "Phòng Công tác Sinh viên",
    "Quy trinh xin tam hoan hoc phi": "Quy trình xin tạm hoãn học phí",
    "Thong bao hoc phi hoc ky 2": "Thông báo học phí học kỳ 2",
    "Thong bao lich dang ky mon hoc": "Thông báo lịch đăng ký môn học",
    "Thong bao hoc bong doanh nghiep": "Thông báo học bổng doanh nghiệp",
    "Quy dinh hoc vu": "Quy định học vụ",
    "Thu thap thong bao cong khai UIT": "Thu thập thông báo công khai UIT",
    "Da duoc duyet tu phieu nop sub-002 va du dieu kien dung trong cau tra loi danh cho sinh vien.": "Đã được duyệt từ phiếu nộp sub-002 và đủ điều kiện dùng trong câu trả lời dành cho sinh viên.",
    "Duoc duyet cho kenh chat sinh vien sau khi xac minh khoang thoi gian hieu luc.": "Được duyệt cho kênh chat sinh viên sau khi xác minh khoảng thời gian hiệu lực.",
    "Detected valid range and academic year from section 1 and 2.": "Đã xác định phạm vi hiệu lực và năm học từ mục 1 và mục 2.",
    "Found fee semester pattern but no explicit valid_until date.": "Đã phát hiện mẫu học phí theo học kỳ nhưng chưa có ngày hết hiệu lực rõ ràng.",
    "No date found. Document kept as archived reference only.": "Không tìm thấy ngày cụ thể. Tài liệu được giữ lại như tài liệu lưu trữ để tra cứu.",
    "Date ranges extracted from heading and bulletin footer.": "Khoảng thời gian được trích từ tiêu đề và chân thông báo.",
    "Archived after new scholarship bulletin superseded it.": "Đã lưu trữ sau khi có thông báo học bổng mới thay thế.",
    "Rejected because the uploaded source does not include an official bulletin body or issue number.": "Từ chối vì nguồn tải lên không có nội dung thông báo chính thức hoặc số hiệu văn bản.",
    "Displayed in public assistant results.": "Được hiển thị trong kết quả trả lời công khai.",
    "Clarified cohort coverage for 2024 intake.": "Làm rõ phạm vi áp dụng cho khóa tuyển sinh 2024.",
    "Updated indexed provenance after operator review.": "Cập nhật nguồn gốc chỉ mục sau khi điều phối viên rà soát.",
    "Initial upload snapshot before operator confirmation.": "Bản chụp ban đầu của lần tải lên trước khi điều phối viên xác nhận.",
    "Initial lecturer snapshot before operator confirmation.": "Bản chụp ban đầu do giảng viên cung cấp trước khi điều phối viên xác nhận.",
    "Approved revision with clarified cohort range and indexing provenance.": "Bản chỉnh sửa đã được duyệt sau khi làm rõ phạm vi khóa và nguồn gốc chỉ mục.",
    "Approved revision with clarified cohort range and updated indexing provenance.": "Bản chỉnh sửa đã được duyệt sau khi làm rõ phạm vi khóa và cập nhật nguồn gốc chỉ mục.",
    "Reviewed publication dates and enrollment timeline from the official source page.": "Đã rà soát ngày công bố và mốc thời gian đăng ký từ trang nguồn chính thức.",
    "Approved from submission sub-002 and now eligible for student-facing assistant answers.": "Đã được duyệt từ phiếu nộp sub-002 và đủ điều kiện dùng trong câu trả lời dành cho sinh viên.",
    "Approved for public student-facing chat after date range verification.": "Được duyệt cho kênh chat sinh viên sau khi xác minh khoảng thời gian hiệu lực.",
    "Published after review approval from submission sub-002.": "Được công bố sau khi duyệt phiếu nộp sub-002.",
    "Expanded cohort coverage to include 2026.": "Mở rộng phạm vi khóa áp dụng để bao gồm năm 2026.",
    "Confirmed publishable validity window through 2026-04-05.": "Xác nhận khoảng hiệu lực có thể công bố đến ngày 2026-04-05.",
    "Preserved as historical reference and later archived.": "Được giữ lại làm tư liệu lịch sử và lưu trữ về sau.",
    "Original scholarship notice preserved as historical reference.": "Thông báo học bổng gốc được lưu làm tư liệu lịch sử.",
    "Archived notice kept for historical scholarship lookups.": "Thông báo lưu trữ vẫn được giữ để tra cứu học bổng trước đây.",
    "Upload completed successfully.": "Tải lên hoàn tất thành công.",
    "Embedding step failed. Retry available.": "Bước tạo embedding thất bại. Có thể thử lại.",
    "Scanning source pages and scheduling updates.": "Đang quét các trang nguồn và lên lịch cập nhật.",
    "Submission accepted by the /web BFF and queued for extraction.": "Phiếu nộp đã được tiếp nhận và đưa vào hàng chờ trích xuất.",
    "Frontend-aligned ingestion contract generated a provisional temporal preview.": "Bản xem trước thời gian hiệu lực được tạo tạm thời từ hợp đồng ingest của frontend.",
}

DOCUMENT_INDEX_EXCERPTS = {
    "doc-001": (
        "Quy định học vụ năm học 2024-2025 áp dụng cho sinh viên các khóa 2022, 2023 và 2024. "
        "Văn bản quy định điều kiện đăng ký học phần, cảnh báo học vụ, tạm dừng học và cách xử lý kết quả học tập theo từng học kỳ. "
        "Hiệu lực từ ngày 01/09/2024 đến hết ngày 31/08/2025."
    ),
    "doc-002": (
        "Thông báo học phí học kỳ 2 dành cho năm học 2025-2026. "
        "Tài liệu nêu nguyên tắc thu học phí theo tín chỉ, mốc nộp học phí và yêu cầu rà soát trước khi công khai cho sinh viên."
    ),
    "doc-003": (
        "Thông báo học bổng doanh nghiệp là tài liệu lưu trữ về các suất học bổng do doanh nghiệp tài trợ. "
        "Văn bản được giữ lại để tra cứu lịch sử và không còn là nguồn áp dụng mới nhất."
    ),
    "doc-004": (
        "Thông báo lịch đăng ký môn học áp dụng trực tiếp cho sinh viên khóa tuyển sinh 2024, 2025 và 2026. "
        "Thời gian đăng ký từ ngày 20/03/2026 đến ngày 05/04/2026. "
        "Sinh viên cần kiểm tra điều kiện tiên quyết, kế hoạch học tập và học phí trước khi xác nhận đăng ký."
    ),
}


def repair_vietnamese_text(value: str) -> str:
    text = str(value)
    for _ in range(2):
        if not any(marker in text for marker in MOJIBAKE_MARKERS):
            break
        try:
            candidate = text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if candidate == text:
            break
        text = candidate
    for source, target in EXACT_TEXT_REPLACEMENTS.items():
        text = text.replace(source, target)
    return " ".join(text.split())


def _normalize_payload_text(value: Any) -> Any:
    if isinstance(value, str):
        return repair_vietnamese_text(value)
    if isinstance(value, list):
        return [_normalize_payload_text(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_payload_text(item) for key, item in value.items()}
    return value


def get_document_index_excerpt(document_id: str) -> str | None:
    excerpt = DOCUMENT_INDEX_EXCERPTS.get(document_id)
    if excerpt is None:
        return None
    return repair_vietnamese_text(excerpt)


def normalize_workspace_state(state: dict[str, Any]) -> dict[str, Any]:
    return _normalize_payload_text(deepcopy(state))

INTERNAL_EMAIL_DOMAIN = "@gm.uit.edu.vn"
ROLE_ROUTE_MATRIX = {
    "guest": {
        "allowed_shells": ["public", "auth", "system"],
        "allowed_routes": ["/", "/chat", "/documents/:id", "/auth/login", "/auth/callback", "/403"],
        "requires_internal_email": False,
    },
    "student": {
        "allowed_shells": ["public", "auth", "system"],
        "allowed_routes": ["/", "/chat", "/documents/:id", "/auth/login", "/auth/callback", "/403"],
        "requires_internal_email": False,
    },
    "teacher": {
        "allowed_shells": ["public", "auth", "app", "system"],
        "allowed_routes": [
            "/",
            "/chat",
            "/documents/:id",
            "/auth/login",
            "/auth/callback",
            "/403",
            "/knowledge",
            "/upload",
        ],
        "requires_internal_email": True,
    },
    "admin": {
        "allowed_shells": ["public", "auth", "app", "admin", "system"],
        "allowed_routes": [
            "/",
            "/chat",
            "/documents/:id",
            "/auth/login",
            "/auth/callback",
            "/403",
            "/knowledge",
            "/upload",
            "/manager",
        ],
        "requires_internal_email": True,
    },
}

SESSION_FIXTURES = {
    "guest": {
        "session_id": "session-guest",
        "status": "anonymous",
        "user": {
            "id": "guest",
            "name": "Guest User",
            "email": "guest@public.uit.edu.vn",
            "role": "guest",
            "department": "Public",
            "avatar_initials": "GU",
        },
    },
    "student": {
        "session_id": "session-student",
        "status": "authenticated",
        "user": {
            "id": "user-student",
            "name": "Nguyen Thi Student",
            "email": "student@gm.uit.edu.vn",
            "role": "student",
            "department": "Student",
            "avatar_initials": "NS",
        },
    },
    "teacher": {
        "session_id": "session-teacher",
        "status": "authenticated",
        "user": {
            "id": "user-teacher",
            "name": "Phạm Văn Lecturer",
            "email": "lecturer@gm.uit.edu.vn",
            "role": "teacher",
            "department": "Khoa Khoa học Máy tính",
            "avatar_initials": "PL",
        },
    },
    "admin": {
        "session_id": "session-admin",
        "status": "authenticated",
        "user": {
            "id": "user-admin",
            "name": "Trần Văn Admin",
            "email": "admin@gm.uit.edu.vn",
            "role": "admin",
            "department": "Quản trị hệ thống",
            "avatar_initials": "TA",
        },
    },
}

DOCUMENT_FIXTURES = [
    {
        "id": "doc-001",
        "title": "Quy định học vụ 2024-2025",
        "owner_name": "Phạm Văn Lecturer",
        "owner_email": "lecturer@gm.uit.edu.vn",
        "lifecycle_status": "approved",
        "processing_status": "completed",
        "created_at": "2026-03-15T08:00:00.000Z",
        "updated_at": "2026-03-16T08:30:00.000Z",
        "temporal_metadata": {
            "document_type": "regulation",
            "extraction_method": "llm",
            "temporal_confidence": 0.93,
            "temporal_reasoning": "Detected valid range and academic year from section 1 and 2.",
            "valid_from": "2024-09-01",
            "valid_until": "2025-08-31",
            "academic_year": "2024-2025",
            "cohort_years": ["2022", "2023", "2024"],
            "document_number": "123/QD-UIT",
            "amends_documents": [],
        },
        "system_metadata": {
            "file_source": "/uploads/quy-dinh-hoc-vu-2024-2025.pdf",
            "indexed_at": "2026-03-16T08:31:00.000Z",
            "content_hash": "4c3a430ec55b4f7509b8d7fc1b03017aa0f84ca4a690d8f0f0c26ee23c0f4aab",
            "is_archived": False,
            "version_number": 2,
        },
        "supplemental_metadata": {
            "title": "Quy định học vụ 2024-2025",
            "issuing_unit": "Phòng Đào tạo Đại học",
            "tags": ["hoc-vu", "quy-che"],
            "visibility_scope": "public",
            "notes": "Được hiển thị trong kết quả trả lời công khai.",
        },
        "traceability": {
            "source_submission_id": None,
            "source_review_id": None,
            "reviewed_by_name": "Lê Thị Operator",
            "published_at": "2026-03-16T08:31:00.000Z",
            "publication_reason": "Bản chỉnh sửa đã được duyệt sau khi làm rõ phạm vi khóa và nguồn gốc chỉ mục.",
        },
        "version_history": [
            {
                "id": "doc-001-v2",
                "version_number": 2,
                "created_at": "2026-03-16T08:31:00.000Z",
                "created_by_name": "Lê Thị Operator",
                "change_summary": "Bản chỉnh sửa đã được duyệt sau khi làm rõ phạm vi khóa và cập nhật nguồn gốc chỉ mục.",
                "file_source": "/uploads/quy-dinh-hoc-vu-2024-2025.pdf",
                "content_hash": "4c3a430ec55b4f7509b8d7fc1b03017aa0f84ca4a690d8f0f0c26ee23c0f4aab",
                "is_current": True,
                "source_submission_id": None,
                "source_review_id": None,
                "change_highlights": [
                    "Làm rõ phạm vi khóa tuyển sinh năm 2024.",
                    "Cập nhật nguồn gốc chỉ mục sau khi quản trị viên rà soát.",
                ],
            },
            {
                "id": "doc-001-v1",
                "version_number": 1,
                "created_at": "2026-03-15T08:05:00.000Z",
                "created_by_name": "Phạm Văn Lecturer",
                "change_summary": "Bản chụp tải lên ban đầu trước khi quản trị viên xác nhận.",
                "file_source": "/uploads/quy-dinh-hoc-vu-2024-2025-v1.pdf",
                "content_hash": "29d9b0f5b6fd38df9065f6ee4b4f15d9d4da045e7c1a5327f1ea9f7eafe83382",
                "is_current": False,
                "source_submission_id": None,
                "source_review_id": None,
                "change_highlights": ["Bản chụp tải lên ban đầu trước khi quản trị viên xác nhận."],
            },
        ],
        "activity_history": [],
    },
    {
        "id": "doc-002",
        "title": "Thông báo học phí học kỳ 2",
        "owner_name": "Lê Thị Operator",
        "owner_email": "operator@gm.uit.edu.vn",
        "lifecycle_status": "pending_review",
        "processing_status": "extracting",
        "created_at": "2026-03-18T04:12:00.000Z",
        "updated_at": "2026-03-18T04:15:00.000Z",
        "temporal_metadata": {
            "document_type": "fee_notice",
            "extraction_method": "regex",
            "temporal_confidence": 0.65,
            "temporal_reasoning": "Found fee semester pattern but no explicit valid_until date.",
            "valid_from": "2026-02-01",
            "valid_until": None,
            "academic_year": "2025-2026",
            "cohort_years": ["2024", "2025"],
            "document_number": None,
            "amends_documents": [],
        },
        "system_metadata": {
            "file_source": "/uploads/thong-bao-hoc-phi-hk2.docx",
            "indexed_at": "2026-03-18T04:16:00.000Z",
            "content_hash": "f73cbe50f57b31cb5db54432f11ce1af2b3f915d7f7068cd1942e84551fdd201",
            "is_archived": False,
            "version_number": 1,
        },
        "supplemental_metadata": {
            "title": "Thông báo học phí học kỳ 2",
            "issuing_unit": "Phòng Kế hoạch - Tài chính",
            "tags": ["hoc-phi"],
            "visibility_scope": "internal",
            "notes": "Đang chờ quản trị viên rà soát trước khi công khai.",
        },
        "traceability": {
            "source_submission_id": None,
            "source_review_id": None,
            "reviewed_by_name": None,
            "published_at": None,
            "publication_reason": None,
        },
        "version_history": [
            {
                "id": "doc-002-v1",
                "version_number": 1,
                "created_at": "2026-03-18T04:16:00.000Z",
                "created_by_name": "Lê Thị Operator",
                "change_summary": "Bản trích xuất ban đầu được tạo từ thông báo DOCX đã tải lên.",
                "file_source": "/uploads/thong-bao-hoc-phi-hk2.docx",
                "content_hash": "f73cbe50f57b31cb5db54432f11ce1af2b3f915d7f7068cd1942e84551fdd201",
                "is_current": True,
                "source_submission_id": None,
                "source_review_id": None,
                "change_highlights": ["Bản trích xuất ban đầu chỉ được giữ lại để rà soát nội bộ."],
            },
        ],
        "activity_history": [
            {
                "id": "audit-004b",
                "actor_name": "Lê Thị Operator",
                "actor_role": "admin",
                "action": "reindex_document",
                "target_type": "document",
                "target_id": "doc-002",
                "target_label": "Thông báo học phí học kỳ 2",
                "created_at": "2026-03-18T04:17:00.000Z",
            },
        ],
    },
    {
        "id": "doc-003",
        "title": "Thông báo học bổng doanh nghiệp",
        "owner_name": "Trần Văn Admin",
        "owner_email": "admin@gm.uit.edu.vn",
        "lifecycle_status": "archived",
        "processing_status": "completed",
        "created_at": "2025-12-10T03:00:00.000Z",
        "updated_at": "2026-02-01T09:20:00.000Z",
        "temporal_metadata": {
            "document_type": "scholarship",
            "extraction_method": "filename_fallback",
            "temporal_confidence": 0.4,
            "temporal_reasoning": "No date found. Document kept as archived reference only.",
            "valid_from": None,
            "valid_until": None,
            "academic_year": None,
            "cohort_years": [],
            "document_number": None,
            "amends_documents": ["HB-2024-12"],
        },
        "system_metadata": {
            "file_source": "/uploads/hoc-bong-doanh-nghiep.pdf",
            "indexed_at": "2025-12-10T03:02:00.000Z",
            "content_hash": "328e12c4cab9798b35fc4fd61ad1da4f3ffdb19b796d328bcb630374ac14f5ab",
            "is_archived": True,
            "version_number": 1,
        },
        "supplemental_metadata": {
            "title": "Thông báo học bổng doanh nghiệp",
            "issuing_unit": "Phòng Công tác Sinh viên",
            "tags": ["hoc-bong"],
            "visibility_scope": "public",
            "notes": "Archived after new scholarship bulletin superseded it.",
        },
        "traceability": {
            "source_submission_id": None,
            "source_review_id": None,
            "reviewed_by_name": "Trần Văn Admin",
            "published_at": "2025-12-10T03:02:00.000Z",
            "publication_reason": "Được giữ lại làm tư liệu lịch sử và lưu trữ sau đó.",
        },
        "version_history": [
            {
                "id": "doc-003-v1",
                "version_number": 1,
                "created_at": "2025-12-10T03:02:00.000Z",
                "created_by_name": "Trần Văn Admin",
                "change_summary": "Thông báo học bổng gốc được lưu làm tư liệu lịch sử.",
                "file_source": "/uploads/hoc-bong-doanh-nghiep.pdf",
                "content_hash": "328e12c4cab9798b35fc4fd61ad1da4f3ffdb19b796d328bcb630374ac14f5ab",
                "is_current": True,
                "source_submission_id": None,
                "source_review_id": None,
                "change_highlights": ["Thông báo lưu trữ vẫn được giữ để tra cứu học bổng trước đây."],
            },
        ],
        "activity_history": [
            {
                "id": "audit-004",
                "actor_name": "Trần Văn Admin",
                "actor_role": "admin",
                "action": "archive_document",
                "target_type": "document",
                "target_id": "doc-003",
                "target_label": "Thông báo học bổng doanh nghiệp",
                "created_at": "2026-02-01T09:20:00.000Z",
            },
        ],
    },
    {
        "id": "doc-004",
        "title": "Thông báo lịch đăng ký môn học",
        "owner_name": "Lê Thị Operator",
        "owner_email": "operator@gm.uit.edu.vn",
        "lifecycle_status": "approved",
        "processing_status": "completed",
        "created_at": "2026-03-17T05:05:00.000Z",
        "updated_at": "2026-03-17T05:40:00.000Z",
        "temporal_metadata": {
            "document_type": "announcement",
            "extraction_method": "regex",
            "temporal_confidence": 0.9,
            "temporal_reasoning": "Đã rà soát ngày công bố và mốc thời gian đăng ký từ trang nguồn chính thức.",
            "valid_from": "2026-03-20",
            "valid_until": "2026-04-05",
            "academic_year": "2025-2026",
            "cohort_years": ["2024", "2025", "2026"],
            "document_number": "88/TB-UIT",
            "amends_documents": [],
        },
        "system_metadata": {
            "file_source": "https://uit.edu.vn/dang-ky-mon-hoc",
            "indexed_at": "2026-03-17T05:33:00.000Z",
            "content_hash": "8c63c494a993d9347615387da779ce3c6b74ff78c08f9f941d190ced6a008fe1",
            "is_archived": False,
            "version_number": 1,
        },
        "supplemental_metadata": {
            "title": "Thông báo lịch đăng ký môn học",
            "issuing_unit": "Phòng Đào tạo Đại học",
            "tags": ["dang-ky-mon-hoc", "thong-bao"],
            "visibility_scope": "public",
            "notes": "Đã được duyệt từ phiếu nộp sub-002 và đủ điều kiện dùng trong câu trả lời dành cho sinh viên.",
        },
        "traceability": {
            "source_submission_id": "sub-002",
            "source_review_id": "review-002",
            "reviewed_by_name": "Lê Thị Operator",
            "published_at": "2026-03-17T05:33:00.000Z",
            "publication_reason": "Được duyệt cho kênh chat sinh viên sau khi xác minh khoảng thời gian hiệu lực.",
        },
        "version_history": [
            {
                "id": "doc-004-v1",
                "version_number": 1,
                "created_at": "2026-03-17T05:33:00.000Z",
                "created_by_name": "Lê Thị Operator",
                "change_summary": "Được công bố sau khi duyệt phiếu nộp sub-002.",
                "file_source": "https://uit.edu.vn/dang-ky-mon-hoc",
                "content_hash": "8c63c494a993d9347615387da779ce3c6b74ff78c08f9f941d190ced6a008fe1",
                "is_current": True,
                "source_submission_id": "sub-002",
                "source_review_id": "review-002",
                "change_highlights": [
                    "Mở rộng phạm vi khóa áp dụng để bao gồm năm 2026.",
                    "Xác nhận khoảng hiệu lực có thể công bố đến ngày 2026-04-05.",
                ],
            },
        ],
        "activity_history": [
            {
                "id": "audit-001",
                "actor_name": "Phạm Văn Lecturer",
                "actor_role": "teacher",
                "action": "upload_submission",
                "target_type": "submission",
                "target_id": "sub-002",
                "target_label": "Thông báo lịch đăng ký môn học",
                "created_at": "2026-03-17T05:05:00.000Z",
            },
            {
                "id": "audit-002",
                "actor_name": "Lê Thị Operator",
                "actor_role": "admin",
                "action": "approve_review",
                "target_type": "review",
                "target_id": "review-002",
                "target_label": "Thông báo lịch đăng ký môn học",
                "created_at": "2026-03-17T05:31:00.000Z",
            },
            {
                "id": "audit-003",
                "actor_name": "Lê Thị Operator",
                "actor_role": "admin",
                "action": "approve_review",
                "target_type": "document",
                "target_id": "doc-004",
                "target_label": "Thông báo lịch đăng ký môn học",
                "created_at": "2026-03-17T05:33:00.000Z",
            },
        ],
    },
]

SUBMISSION_FIXTURES = [
    {
        "id": "sub-001",
        "title": "Quy trinh xin tam hoan hoc phi",
        "source_type": "file",
        "lifecycle_status": "pending_review",
        "processing_status": "indexing",
        "created_at": "2026-03-19T01:15:00.000Z",
        "updated_at": "2026-03-19T01:22:00.000Z",
        "linked_document_id": None,
        "temporal_metadata": {
            "document_type": "procedure",
            "extraction_method": "llm",
            "temporal_confidence": 0.81,
            "temporal_reasoning": "Tiêu đề quy trình và các đề mục xác nhận loại tài liệu.",
            "valid_from": "2026-03-01",
            "valid_until": None,
            "academic_year": None,
            "cohort_years": ["2022", "2023", "2024", "2025"],
            "document_number": "15/TB-UIT",
            "amends_documents": [],
        },
        "system_metadata": {
            "file_source": "/uploads/tam-hoan-hoc-phi.pdf",
            "indexed_at": "2026-03-19T01:23:00.000Z",
            "content_hash": "dfa6f9929ce630f6f2dfe69287a5f44cab7efb3f7276513c4d641b12311cb5ce",
            "is_archived": False,
            "version_number": 1,
        },
        "supplemental_metadata": {
            "title": "Quy trinh xin tam hoan hoc phi",
            "issuing_unit": "Phòng Đào tạo Đại học",
            "tags": ["hoc-phi", "thu-tuc"],
            "visibility_scope": "internal",
            "notes": "Được giảng viên tải lên và đang chờ rà soát.",
        },
        "traceability": {
            "review_task_id": "review-001",
            "published_document_id": None,
            "reviewed_by_name": "Lê Thị Operator",
            "published_at": None,
            "publication_reason": "Đang chờ xác nhận phạm vi khóa trước khi công bố.",
        },
    },
    {
        "id": "sub-002",
        "title": "Thông báo lịch đăng ký môn học",
        "source_type": "url",
        "lifecycle_status": "approved",
        "processing_status": "completed",
        "created_at": "2026-03-17T05:05:00.000Z",
        "updated_at": "2026-03-17T05:32:00.000Z",
        "linked_document_id": "doc-004",
        "temporal_metadata": {
            "document_type": "announcement",
            "extraction_method": "regex",
            "temporal_confidence": 0.88,
            "temporal_reasoning": "Date ranges extracted from heading and bulletin footer.",
            "valid_from": "2026-03-20",
            "valid_until": "2026-04-05",
            "academic_year": "2025-2026",
            "cohort_years": ["2024", "2025"],
            "document_number": "88/TB-UIT",
            "amends_documents": [],
        },
        "system_metadata": {
            "file_source": "https://uit.edu.vn/dang-ky-mon-hoc",
            "indexed_at": "2026-03-17T05:33:00.000Z",
            "content_hash": "e8de316dbbb9ed2f2ec665cc9070b6ff861adf4a27574f5f46320fe0bbaf9998",
            "is_archived": False,
            "version_number": 1,
        },
        "supplemental_metadata": {
            "title": "Thông báo lịch đăng ký môn học",
            "issuing_unit": "Phòng Đào tạo Đại học",
            "tags": ["dang-ky-mon-hoc"],
            "visibility_scope": "public",
            "notes": "Đã công bố cho kênh chat dành cho sinh viên.",
        },
        "traceability": {
            "review_task_id": "review-002",
            "published_document_id": "doc-004",
            "reviewed_by_name": "Lê Thị Operator",
            "published_at": "2026-03-17T05:33:00.000Z",
            "publication_reason": "Được duyệt cho kênh chat sinh viên sau khi xác minh khoảng thời gian hiệu lực.",
        },
    },
]

REVIEW_FIXTURES = [
    {
        "id": "review-001",
        "submission_id": "sub-001",
        "published_document_id": None,
        "title": "Quy trinh xin tam hoan hoc phi",
        "source_type": "file",
        "visibility_scope": "internal",
        "submitted_by_name": "Phạm Văn Lecturer",
        "submitted_by_email": "lecturer@gm.uit.edu.vn",
        "reviewer_name": "Lê Thị Operator",
        "status": "pending_review",
        "confidence": 0.81,
        "created_at": "2026-03-19T02:10:00.000Z",
        "extracted_temporal_metadata": deepcopy(SUBMISSION_FIXTURES[0]["temporal_metadata"]),
        "edited_temporal_metadata": {
            **deepcopy(SUBMISSION_FIXTURES[0]["temporal_metadata"]),
            "cohort_years": ["2023", "2024", "2025"],
        },
        "reason": "Cần xác nhận lại phạm vi khóa trước khi công bố.",
    },
    {
        "id": "review-002",
        "submission_id": "sub-002",
        "published_document_id": "doc-004",
        "title": "Thông báo lịch đăng ký môn học",
        "source_type": "url",
        "visibility_scope": "public",
        "submitted_by_name": "Phạm Văn Lecturer",
        "submitted_by_email": "lecturer@gm.uit.edu.vn",
        "reviewer_name": "Lê Thị Operator",
        "status": "approved",
        "confidence": 0.88,
        "created_at": "2026-03-17T05:20:00.000Z",
        "extracted_temporal_metadata": deepcopy(SUBMISSION_FIXTURES[1]["temporal_metadata"]),
        "edited_temporal_metadata": {
            **deepcopy(SUBMISSION_FIXTURES[1]["temporal_metadata"]),
            "cohort_years": ["2024", "2025", "2026"],
        },
        "reason": "Được duyệt cho kênh chat sinh viên sau khi xác minh khoảng thời gian hiệu lực.",
    },
    {
        "id": "review-003",
        "submission_id": "sub-001",
        "published_document_id": None,
        "title": "Thông báo học phí học kỳ 2",
        "source_type": "file",
        "visibility_scope": "internal",
        "submitted_by_name": "Phạm Văn Lecturer",
        "submitted_by_email": "lecturer@gm.uit.edu.vn",
        "reviewer_name": "Lê Thị Operator",
        "status": "rejected",
        "confidence": 0.42,
        "created_at": "2026-03-18T09:10:00.000Z",
        "extracted_temporal_metadata": {
            "document_type": "fee_notice",
            "extraction_method": "filename_fallback",
            "temporal_confidence": 0.42,
            "temporal_reasoning": "Only filename and scattered semester keywords were detected.",
            "valid_from": None,
            "valid_until": None,
            "academic_year": None,
            "cohort_years": [],
            "document_number": None,
            "amends_documents": [],
        },
        "edited_temporal_metadata": {
            "document_type": "fee_notice",
            "extraction_method": "filename_fallback",
            "temporal_confidence": 0.42,
            "temporal_reasoning": "Only filename and scattered semester keywords were detected.",
            "valid_from": None,
            "valid_until": None,
            "academic_year": None,
            "cohort_years": [],
            "document_number": None,
            "amends_documents": [],
        },
        "reason": "Rejected because the uploaded source does not include an official bulletin body or issue number.",
    },
]

JOB_FIXTURES = [
    {
        "id": "job-001",
        "type": "upload",
        "status": "completed",
        "progress": 100,
            "related_title": "Quy định học vụ 2024-2025",
        "started_at": "2026-03-16T08:28:00.000Z",
        "updated_at": "2026-03-16T08:31:00.000Z",
        "message": "Upload completed successfully.",
    },
    {
        "id": "job-002",
        "type": "indexing",
        "status": "failed",
        "progress": 62,
        "related_title": "Quy trinh xin tam hoan hoc phi",
        "started_at": "2026-03-19T01:20:00.000Z",
        "updated_at": "2026-03-19T01:23:00.000Z",
        "message": "Embedding step failed. Retry available.",
    },
    {
        "id": "job-003",
        "type": "scan",
        "status": "indexing",
        "progress": 48,
            "related_title": "Thu thập thông báo công khai UIT",
        "started_at": "2026-03-20T02:00:00.000Z",
        "updated_at": "2026-03-20T02:12:00.000Z",
        "message": "Scanning source pages and scheduling updates.",
    },
]

ADMIN_USER_FIXTURES = [
    {
        "id": "usr-001",
        "name": "Nguyễn Minh Student",
        "email": "student@uit.edu.vn",
        "role": "student",
        "status": "active",
        "scope": "student_portal",
        "last_active_at": "2026-03-20T07:10:00.000Z",
        "is_internal_domain_compliant": True,
    },
    {
        "id": "usr-002",
        "name": "Phạm Văn Lecturer",
        "email": "lecturer@gm.uit.edu.vn",
        "role": "teacher",
        "status": "active",
        "scope": "teacher_workspace",
        "last_active_at": "2026-03-20T06:42:00.000Z",
        "is_internal_domain_compliant": True,
    },
    {
        "id": "usr-003",
        "name": "Lê Thị Operator",
        "email": "operator@gm.uit.edu.vn",
        "role": "admin",
        "status": "active",
        "scope": "admin_console",
        "last_active_at": "2026-03-20T06:58:00.000Z",
        "is_internal_domain_compliant": True,
    },
    {
        "id": "usr-004",
        "name": "Trần Văn Admin",
        "email": "admin@gm.uit.edu.vn",
        "role": "admin",
        "status": "active",
        "scope": "admin_console",
        "last_active_at": "2026-03-20T05:55:00.000Z",
        "is_internal_domain_compliant": True,
    },
    {
        "id": "usr-006",
        "name": "22520807",
        "email": "22520807@gm.uit.edu.vn",
        "role": "admin",
        "status": "active",
        "scope": "admin_console",
        "last_active_at": "2026-04-11T06:00:00.000Z",
        "is_internal_domain_compliant": True,
    },
    {
        "id": "usr-005",
        "name": "Mời giảng viên đang chờ",
        "email": "pending-teacher@gm.uit.edu.vn",
        "role": "teacher",
        "status": "invited",
        "scope": "teacher_workspace",
        "last_active_at": "2026-03-18T02:10:00.000Z",
        "is_internal_domain_compliant": True,
    },
]

SYSTEM_SETTING_FIXTURES = [
    {
        "group": "auth",
        "key": "sso_provider",
        "label": "Nhà cung cấp SSO cho giảng viên",
        "value": "UIT Google Workspace SSO",
        "description": "Tài khoản nội bộ phải xác thực qua SSO chính thức của trường.",
        "is_sensitive": False,
        "source": "mock_policy",
    },
    {
        "group": "auth",
        "key": "internal_domain_rule",
        "label": "Quy tắc domain nội bộ",
        "value": "teacher/admin bắt buộc dùng @gm.uit.edu.vn",
        "description": "Vai trò cộng tác viên và quản trị chỉ hợp lệ khi dùng email của trường.",
        "is_sensitive": False,
        "source": "derived_contract",
    },
    {
        "group": "ingestion",
        "key": "publication_gate",
        "label": "Cổng công bố",
        "value": "Phải được duyệt trước khi công khai",
        "description": "Tài liệu do giảng viên tải lên chỉ là tạm thời cho đến khi quản trị viên duyệt.",
        "is_sensitive": False,
        "source": "derived_contract",
    },
    {
        "group": "publication",
        "key": "admin_break_glass_override",
        "label": "Quyền can thiệp khẩn cấp của quản trị",
        "value": "Quản trị viên sở hữu thao tác duyệt, lưu trữ, đánh chỉ mục lại và thử lại, kèm nhật ký đầy đủ",
        "description": "Các thao tác duyệt, lưu trữ, đánh chỉ mục lại và thử lại phải do quản trị viên thực hiện và luôn được ghi nhận.",
        "is_sensitive": False,
        "source": "derived_contract",
    },
    {
        "group": "publication",
        "key": "system_api_key",
        "label": "Khóa bí mật cho luồng ingest backend",
        "value": "stored-in-secret-manager",
        "description": "Thông tin xác thực được quản lý ở phía server và không bao giờ hiển thị thô trên frontend.",
        "is_sensitive": True,
        "source": "mock_policy",
    },
    {
        "group": "chat",
        "key": "citation_policy",
        "label": "Chính sách trích dẫn",
        "value": "Câu trả lời dành cho sinh viên phải hiển thị nguồn tham chiếu và cảnh báo",
        "description": "Nguồn có độ tin cậy thấp, đang chờ duyệt hoặc đã lưu trữ phải hiển thị cảnh báo rõ ràng trên giao diện.",
        "is_sensitive": False,
        "source": "derived_contract",
    },
]

AUDIT_LOG_FIXTURES = [
    {
        "id": "audit-001",
        "actor_name": "Phạm Văn Lecturer",
        "actor_role": "teacher",
        "action": "upload_submission",
        "target_type": "submission",
        "target_id": "sub-002",
        "target_label": "Thông báo lịch đăng ký môn học",
        "created_at": "2026-03-17T05:05:00.000Z",
    },
    {
        "id": "audit-002",
        "actor_name": "Lê Thị Operator",
        "actor_role": "admin",
        "action": "approve_review",
        "target_type": "review",
        "target_id": "review-002",
        "target_label": "Thông báo lịch đăng ký môn học",
        "created_at": "2026-03-17T05:31:00.000Z",
    },
    {
        "id": "audit-003",
        "actor_name": "Lê Thị Operator",
        "actor_role": "admin",
        "action": "approve_review",
        "target_type": "document",
        "target_id": "doc-004",
        "target_label": "Thông báo lịch đăng ký môn học",
        "created_at": "2026-03-17T05:33:00.000Z",
    },
    {
        "id": "audit-004",
        "actor_name": "Trần Văn Admin",
        "actor_role": "admin",
        "action": "archive_document",
        "target_type": "document",
        "target_id": "doc-003",
        "target_label": "Thông báo học bổng doanh nghiệp",
        "created_at": "2026-02-01T09:20:00.000Z",
    },
    {
        "id": "audit-004b",
        "actor_name": "Lê Thị Operator",
        "actor_role": "admin",
        "action": "reindex_document",
        "target_type": "document",
        "target_id": "doc-002",
        "target_label": "Thông báo học phí học kỳ 2",
        "created_at": "2026-03-18T04:17:00.000Z",
    },
    {
        "id": "audit-005",
        "actor_name": "Trần Văn Admin",
        "actor_role": "admin",
        "action": "role_switch",
        "target_type": "session",
        "target_id": "session-admin",
        "target_label": "Chuyển vai trò demo sang admin",
        "created_at": "2026-03-20T07:30:00.000Z",
    },
]

DENSE_AUDIT_LOG_FIXTURES = [
    {
        "id": "audit-000",
        "actor_name": "Nguyễn Minh Student",
        "actor_role": "student",
        "action": "login",
        "target_type": "session",
        "target_id": "session-student",
        "target_label": "Phiên cổng sinh viên",
        "created_at": "2026-03-20T06:15:00.000Z",
    },
    *deepcopy(AUDIT_LOG_FIXTURES),
    {
        "id": "audit-006",
        "actor_name": "Lê Thị Operator",
        "actor_role": "admin",
        "action": "reject_review",
        "target_type": "review",
        "target_id": "review-003",
        "target_label": "Thông báo học phí học kỳ 2",
        "created_at": "2026-03-18T16:15:00.000Z",
    },
]

CONVERSATION_FIXTURES: list[dict] = []


def build_initial_state() -> dict:
    return normalize_workspace_state({
        "sessions": deepcopy(SESSION_FIXTURES),
        "documents": deepcopy(DOCUMENT_FIXTURES),
        "submissions": deepcopy(SUBMISSION_FIXTURES),
        "reviews": deepcopy(REVIEW_FIXTURES),
        "jobs": deepcopy(JOB_FIXTURES),
        "admin_users": deepcopy(ADMIN_USER_FIXTURES),
        "role_policies": [
            {
                "role": role,
                "allowed_shells": deepcopy(policy["allowed_shells"]),
                "allowed_routes": deepcopy(policy["allowed_routes"]),
                "requires_internal_email": policy["requires_internal_email"],
            }
            for role, policy in ROLE_ROUTE_MATRIX.items()
        ],
        "system_settings": deepcopy(SYSTEM_SETTING_FIXTURES),
        "audit_logs": deepcopy(AUDIT_LOG_FIXTURES),
        "dense_audit_logs": deepcopy(DENSE_AUDIT_LOG_FIXTURES),
        "conversations": deepcopy(CONVERSATION_FIXTURES),
    })
