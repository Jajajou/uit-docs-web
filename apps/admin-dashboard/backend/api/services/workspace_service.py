"""In-memory BFF service used by the /web backend and its tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from api.errors import ApiServiceError
from api.schemas import Role
from api.services.fixtures import INTERNAL_EMAIL_DOMAIN, build_initial_state

INTERNAL_ROLES = {"lecturer", "operator", "admin"}


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class InMemoryWorkspaceService:
    """Provides contract-aligned data without external dependencies."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        state = build_initial_state()
        self.sessions = state["sessions"]
        self.issued_session_tokens: dict[str, dict[str, str]] = {}
        self.pending_sso_states: dict[str, dict[str, str]] = {}
        self.documents = state["documents"]
        self.submissions = state["submissions"]
        self.reviews = state["reviews"]
        self.jobs = state["jobs"]
        self.admin_users = state["admin_users"]
        self.role_policies = state["role_policies"]
        self.system_settings = state["system_settings"]
        self.audit_logs = state["audit_logs"]
        self.dense_audit_logs = state["dense_audit_logs"]
        self.conversations = state["conversations"]

    def _raise(self, status_code: int, code: str, message: str, details: Any = None) -> None:
        raise ApiServiceError(status_code=status_code, code=code, message=message, details=details)

    def _find_by_id(self, items: list[dict], item_id: str, error_code: str, message: str) -> dict:
        for item in items:
            if item["id"] == item_id:
                return item
        self._raise(404, error_code, message)

    def _actor(self, role: Role) -> dict:
        return deepcopy(self.sessions[role]["user"])

    def _make_compliance(self, role: str, email: str) -> bool:
        return role not in INTERNAL_ROLES or email.lower().endswith(INTERNAL_EMAIL_DOMAIN)

    def _build_document_version_entry(
        self,
        *,
        document_id: str,
        version_number: int,
        created_at: str,
        created_by_name: str,
        change_summary: str,
        file_source: str,
        content_hash: str,
        is_current: bool,
        source_submission_id: str | None = None,
        source_review_id: str | None = None,
        change_highlights: list[str] | None = None,
    ) -> dict:
        return {
            "id": f"{document_id}-v{version_number}",
            "version_number": version_number,
            "created_at": created_at,
            "created_by_name": created_by_name,
            "change_summary": change_summary,
            "file_source": file_source,
            "content_hash": content_hash,
            "is_current": is_current,
            "source_submission_id": source_submission_id,
            "source_review_id": source_review_id,
            "change_highlights": change_highlights or [],
        }

    def _build_document_activity_entry(
        self,
        *,
        entry_id: str,
        actor_name: str,
        actor_role: Role,
        action: str,
        target_type: str,
        target_id: str,
        target_label: str,
        created_at: str,
    ) -> dict:
        return {
            "id": entry_id,
            "actor_name": actor_name,
            "actor_role": actor_role,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "target_label": target_label,
            "created_at": created_at,
        }

    def _build_temporal_change_highlights(
        self,
        previous_temporal: dict | None,
        next_temporal: dict,
        *,
        visibility_scope: str | None = None,
    ) -> list[str]:
        highlights: list[str] = []
        baseline = previous_temporal or {}

        def append_if_changed(key: str, label: str, formatter=lambda value: value):
            previous_value = formatter(baseline.get(key))
            next_value = formatter(next_temporal.get(key))
            if previous_value != next_value and next_value not in (None, "", []):
                highlights.append(f"{label} updated to {next_value}.")

        append_if_changed("document_type", "Document type")
        append_if_changed("valid_from", "Valid from")
        append_if_changed("valid_until", "Valid until")
        append_if_changed("academic_year", "Academic year")
        append_if_changed("document_number", "Document number")
        append_if_changed("cohort_years", "Cohort coverage", lambda value: ", ".join(value or []))

        if visibility_scope == "public":
            highlights.append("Marked as eligible for public student-facing citation.")
        elif visibility_scope == "internal":
            highlights.append("Retained for internal staff use only.")

        if not highlights:
            highlights.append("Metadata verified without material change.")

        return highlights[:4]

    def get_session(self, role: Role, scenario: str) -> dict:
        if scenario == "auth-error":
            self._raise(500, "auth_fetch_failed", "Unable to validate the current session.")
        if scenario == "forbidden":
            self._raise(403, "forbidden", "Access denied for this mock scenario.")

        session = deepcopy(self.sessions[role])
        if scenario == "non-compliant-internal-email" and role in INTERNAL_ROLES:
            session["user"]["email"] = f"{role}@uit.edu.vn"
        return session

    def issue_session_token(self, role: Role, auth_method: str = "demo_bootstrap") -> str:
        token = f"uit-session-{uuid4().hex}"
        self.issued_session_tokens[token] = {"role": role, "auth_method": auth_method}
        return token

    def resolve_session_role(self, token: str | None) -> Role | None:
        if not token:
            return None
        session = self.issued_session_tokens.get(token)
        if session is None:
            return None
        if isinstance(session, str):
            return session
        role = session.get("role")
        return role if role in {"guest", "student", "lecturer", "operator", "admin"} else None

    def revoke_session_token(self, token: str | None) -> None:
        if token:
            self.issued_session_tokens.pop(token, None)

    def issue_sso_state(self, return_to: str | None, scenario: str = "happy") -> str:
        state = f"sso-{uuid4().hex}"
        self.pending_sso_states[state] = {
            "return_to": return_to or "",
            "scenario": scenario,
            "created_at": utc_now_iso(),
        }
        return state

    def read_sso_state(self, state: str) -> dict[str, str] | None:
        stored = self.pending_sso_states.get(state)
        return deepcopy(stored) if stored else None

    def consume_sso_state(self, state: str) -> dict[str, str] | None:
        stored = self.pending_sso_states.pop(state, None)
        return deepcopy(stored) if stored else None

    def list_documents(
        self,
        scenario: str,
        search: str | None = None,
        lifecycle_status: str | None = None,
        visibility_scope: str | None = None,
    ) -> list[dict]:
        if scenario == "error":
            self._raise(500, "document_fetch_failed", "Unable to load document library.")

        documents = deepcopy(self.documents)
        if scenario == "empty":
            documents = []
        elif scenario == "archived-doc":
            documents = [document for document in documents if document["system_metadata"]["is_archived"]]

        if search:
            needle = search.lower()
            documents = [
                document
                for document in documents
                if needle in document["title"].lower()
                or needle in document["supplemental_metadata"]["issuing_unit"].lower()
                or any(needle in tag.lower() for tag in document["supplemental_metadata"]["tags"])
            ]
        if lifecycle_status:
            documents = [document for document in documents if document["lifecycle_status"] == lifecycle_status]
        if visibility_scope:
            documents = [
                document for document in documents if document["supplemental_metadata"]["visibility_scope"] == visibility_scope
            ]
        return documents

    def get_document(self, document_id: str, scenario: str) -> dict:
        documents = self.list_documents(scenario)
        for document in documents:
            if document["id"] == document_id:
                return document
        self._raise(404, "document_not_found", "Document not found.")

    def archive_document(self, document_id: str, actor_role: Role) -> dict:
        document = self._find_by_id(self.documents, document_id, "document_not_found", "Document not found.")
        now = utc_now_iso()
        document["lifecycle_status"] = "archived"
        document["system_metadata"]["is_archived"] = True
        document["updated_at"] = now
        document["system_metadata"]["indexed_at"] = now
        actor = self._actor(actor_role)
        audit_entry = self._build_document_activity_entry(
            entry_id=f"audit-{uuid4().hex[:8]}",
            actor_name=actor["name"],
            actor_role=actor_role,
            action="archive_document",
            target_type="document",
            target_id=document_id,
            target_label=document["title"],
            created_at=now,
        )
        self.audit_logs.insert(0, audit_entry)
        document.setdefault("activity_history", []).insert(0, deepcopy(audit_entry))
        return deepcopy(document)

    def reindex_document(self, document_id: str, actor_role: Role) -> dict:
        document = self._find_by_id(self.documents, document_id, "document_not_found", "Document not found.")
        now = utc_now_iso()
        document["processing_status"] = "indexing"
        document["updated_at"] = now
        self.jobs.insert(
            0,
            {
                "id": f"job-{uuid4().hex[:8]}",
                "type": "indexing",
                "status": "indexing",
                "progress": 12,
                "related_title": document["title"],
                "started_at": now,
                "updated_at": now,
                "message": "Reindex triggered from document action.",
            },
        )
        actor = self._actor(actor_role)
        audit_entry = self._build_document_activity_entry(
            entry_id=f"audit-{uuid4().hex[:8]}",
            actor_name=actor["name"],
            actor_role=actor_role,
            action="reindex_document",
            target_type="document",
            target_id=document_id,
            target_label=document["title"],
            created_at=now,
        )
        self.audit_logs.insert(0, audit_entry)
        document.setdefault("activity_history", []).insert(0, deepcopy(audit_entry))
        return deepcopy(document)

    def list_submissions(self, scenario: str, lifecycle_status: str | None = None) -> list[dict]:
        submissions = deepcopy(self.submissions)
        if scenario == "empty":
            submissions = []
        if lifecycle_status:
            submissions = [submission for submission in submissions if submission["lifecycle_status"] == lifecycle_status]
        return submissions

    def get_submission(self, submission_id: str, scenario: str) -> dict:
        submissions = self.list_submissions(scenario)
        for submission in submissions:
            if submission["id"] == submission_id:
                return submission
        self._raise(404, "submission_not_found", "Submission not found.")

    def create_submission(self, payload: dict, scenario: str, actor_role: Role) -> dict:
        if scenario == "duplicate-upload":
            self._raise(
                409,
                "duplicate_document",
                "A document with the same content hash already exists.",
                details={"conflictingDocumentId": "doc-001"},
            )

        now = utc_now_iso()
        source_type = payload.get("sourceType", "file")
        title = payload.get("title") or "Untitled submission"
        content_hash = sha256(f"{title}|{payload.get('fileName') or payload.get('url') or payload.get('content') or now}".encode()).hexdigest()
        visibility_scope = payload.get("visibilityScope") or "internal"
        tags = payload.get("tags") or []
        notes = payload.get("notes") or "Submitted from the /web contributor workflow."
        issuing_unit = payload.get("issuingUnit") or self._actor(actor_role)["department"]
        file_source = payload.get("url") or f"/uploads/{payload.get('fileName') or title.lower().replace(' ', '-')}.bin"

        temporal_metadata = {
            "document_type": "procedure" if source_type == "file" else "announcement",
            "extraction_method": "llm" if source_type != "url" else "regex",
            "temporal_confidence": 0.81,
            "temporal_reasoning": "Frontend-aligned ingestion contract generated a provisional temporal preview.",
            "valid_from": None,
            "valid_until": None,
            "academic_year": None,
            "cohort_years": [],
            "document_number": None,
            "amends_documents": [],
        }
        if scenario == "low-confidence":
            temporal_metadata.update({"document_type": "other", "temporal_confidence": 0.0, "temporal_reasoning": ""})

        review_id = f"review-{uuid4().hex[:8]}"
        submission = {
            "id": f"sub-{uuid4().hex[:8]}",
            "title": title,
            "source_type": source_type,
            "lifecycle_status": "pending_review",
            "processing_status": "uploading",
            "created_at": now,
            "updated_at": now,
            "linked_document_id": None,
            "temporal_metadata": temporal_metadata,
            "system_metadata": {
                "file_source": file_source,
                "indexed_at": now,
                "content_hash": content_hash,
                "is_archived": False,
                "version_number": 1,
            },
            "supplemental_metadata": {
                "title": title,
                "issuing_unit": issuing_unit,
                "tags": tags,
                "visibility_scope": visibility_scope,
                "notes": notes,
            },
            "traceability": {
                "review_task_id": review_id,
                "published_document_id": None,
                "reviewed_by_name": "Le Thi Operator",
                "published_at": None,
                "publication_reason": notes,
            },
        }
        self.submissions.insert(0, submission)
        self.jobs.insert(
            0,
            {
                "id": f"job-{uuid4().hex[:8]}",
                "type": "upload",
                "status": "uploading",
                "progress": 15,
                "related_title": title,
                "started_at": now,
                "updated_at": now,
                "message": "Submission accepted by the /web BFF and queued for extraction.",
            },
        )
        actor = self._actor(actor_role)
        self.reviews.insert(
            0,
            {
                "id": review_id,
                "submission_id": submission["id"],
                "published_document_id": None,
                "title": submission["title"],
                "source_type": submission["source_type"],
                "visibility_scope": submission["supplemental_metadata"]["visibility_scope"],
                "submitted_by_name": actor["name"],
                "submitted_by_email": actor["email"],
                "reviewer_name": "Le Thi Operator",
                "status": "pending_review",
                "confidence": submission["temporal_metadata"]["temporal_confidence"],
                "created_at": now,
                "extracted_temporal_metadata": deepcopy(submission["temporal_metadata"]),
                "edited_temporal_metadata": deepcopy(submission["temporal_metadata"]),
                "reason": notes,
            },
        )
        self.audit_logs.insert(
            0,
            {
                "id": f"audit-{uuid4().hex[:8]}",
                "actor_name": actor["name"],
                "actor_role": actor_role,
                "action": "upload_submission",
                "target_type": "submission",
                "target_id": submission["id"],
                "target_label": submission["title"],
                "created_at": now,
            },
        )
        return deepcopy(submission)

    def list_reviews(self, scenario: str, status: str | None = None) -> list[dict]:
        reviews = deepcopy(self.reviews)
        if scenario == "empty":
            reviews = []
        if status:
            reviews = [review for review in reviews if review["status"] == status]
        return reviews

    def apply_review_decision(self, review_id: str, payload: dict, actor_role: Role) -> dict:
        review = self._find_by_id(self.reviews, review_id, "review_not_found", "Review task not found.")
        submission = self._find_by_id(
            self.submissions,
            review["submission_id"],
            "submission_not_found",
            "Submission linked to this review was not found.",
        )

        next_status = payload["status"]
        now = utc_now_iso()
        review["status"] = next_status
        if payload.get("reason"):
            review["reason"] = payload["reason"]
        if payload.get("edited_temporal_metadata"):
            review["edited_temporal_metadata"] = payload["edited_temporal_metadata"]

        submission["lifecycle_status"] = next_status
        submission["updated_at"] = now
        submission.setdefault("traceability", {})
        submission["traceability"].update(
            {
                "review_task_id": review_id,
                "reviewed_by_name": review["reviewer_name"],
                "publication_reason": review["reason"],
            }
        )
        if next_status == "approved":
            submission["processing_status"] = "completed"
            published_document_id = review.get("published_document_id") or f"doc-{uuid4().hex[:8]}"
            review["published_document_id"] = published_document_id
            submission["linked_document_id"] = published_document_id
            submission["traceability"].update(
                {
                    "published_document_id": published_document_id,
                    "published_at": now,
                }
            )
            document = next((item for item in self.documents if item["id"] == published_document_id), None)
            previous_versions = deepcopy(document.get("version_history", [])) if document else []
            for version_entry in previous_versions:
                version_entry["is_current"] = False
            next_version_number = (document["system_metadata"]["version_number"] if document else 0) + 1
            submission_system_metadata = deepcopy(submission["system_metadata"])
            submission_system_metadata["version_number"] = next_version_number
            submission_system_metadata["indexed_at"] = now
            previous_temporal = document["temporal_metadata"] if document else review["extracted_temporal_metadata"]
            change_highlights = self._build_temporal_change_highlights(
                previous_temporal,
                review["edited_temporal_metadata"],
                visibility_scope=submission["supplemental_metadata"]["visibility_scope"],
            )
            document_payload = {
                "id": published_document_id,
                "title": submission["title"],
                "owner_name": review["submitted_by_name"],
                "owner_email": review["submitted_by_email"],
                "lifecycle_status": "approved",
                "processing_status": "completed",
                "created_at": submission["created_at"],
                "updated_at": now,
                "temporal_metadata": deepcopy(review["edited_temporal_metadata"]),
                "system_metadata": submission_system_metadata,
                "supplemental_metadata": deepcopy(submission["supplemental_metadata"]),
                "traceability": {
                    "source_submission_id": submission["id"],
                    "source_review_id": review_id,
                    "reviewed_by_name": review["reviewer_name"],
                    "published_at": now,
                    "publication_reason": review["reason"],
                },
                "version_history": [
                    self._build_document_version_entry(
                        document_id=published_document_id,
                        version_number=next_version_number,
                        created_at=now,
                        created_by_name=actor_role == "admin" and "Tran Van Admin" or review["reviewer_name"],
                        change_summary=review["reason"] or "Published after review approval.",
                        file_source=submission_system_metadata["file_source"],
                        content_hash=submission_system_metadata["content_hash"],
                        is_current=True,
                        source_submission_id=submission["id"],
                        source_review_id=review_id,
                        change_highlights=change_highlights,
                    ),
                    *previous_versions,
                ],
                "activity_history": deepcopy(document.get("activity_history", [])) if document else [],
            }
            if document:
                document.update(document_payload)
            else:
                self.documents.append(document_payload)
            action = "approve_review"
        elif next_status == "rejected":
            submission["processing_status"] = "failed"
            submission["linked_document_id"] = None
            review["published_document_id"] = None
            submission["traceability"].update(
                {
                    "published_document_id": None,
                    "published_at": None,
                }
            )
            action = "reject_review"
        else:
            submission["processing_status"] = "indexing"
            submission["linked_document_id"] = None
            review["published_document_id"] = None
            submission["traceability"].update(
                {
                    "published_document_id": None,
                    "published_at": None,
                }
            )
            action = "request_changes"

        actor = self._actor(actor_role)
        audit_entry = self._build_document_activity_entry(
            entry_id=f"audit-{uuid4().hex[:8]}",
            actor_name=actor["name"],
            actor_role=actor_role,
            action=action,
            target_type="review",
            target_id=review_id,
            target_label=review["title"],
            created_at=now,
        )
        self.audit_logs.insert(0, audit_entry)
        if next_status == "approved" and review.get("published_document_id"):
            published_document = self._find_by_id(
                self.documents,
                review["published_document_id"],
                "document_not_found",
                "Published document not found.",
            )
            published_document.setdefault("activity_history", []).insert(0, deepcopy(audit_entry))
        return deepcopy(review)

    def list_jobs(self, scenario: str, status: str | None = None, job_type: str | None = None) -> list[dict]:
        jobs = deepcopy(self.jobs)
        if scenario == "failed-job":
            jobs = [job for job in jobs if job["status"] == "failed"]
        elif scenario == "empty":
            jobs = []
        if status:
            jobs = [job for job in jobs if job["status"] == status]
        if job_type:
            jobs = [job for job in jobs if job["type"] == job_type]
        return jobs

    def retry_job(self, job_id: str) -> dict:
        job = self._find_by_id(self.jobs, job_id, "job_not_found", "Job not found.")
        job["status"] = "indexing"
        job["progress"] = 15
        job["updated_at"] = utc_now_iso()
        job["message"] = "Retry accepted by the /web BFF."
        return deepcopy(job)

    def list_admin_users(
        self,
        scenario: str,
        role_filter: str | None = None,
        status_filter: str | None = None,
        compliance: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        if scenario == "error":
            self._raise(500, "admin_user_fetch_failed", "Unable to load admin users.")

        users = deepcopy(self.admin_users)
        if scenario == "empty":
            users = []
        elif scenario == "non-compliant-internal-email":
            for user in users:
                if user["id"] == "usr-005":
                    user["email"] = "pending-lecturer@gmail.com"
                    user["is_internal_domain_compliant"] = False

        if role_filter:
            users = [user for user in users if user["role"] == role_filter]
        if status_filter:
            users = [user for user in users if user["status"] == status_filter]
        if compliance == "compliant":
            users = [user for user in users if user["is_internal_domain_compliant"]]
        if compliance == "non_compliant":
            users = [user for user in users if not user["is_internal_domain_compliant"]]
        if search:
            needle = search.lower()
            users = [user for user in users if needle in user["name"].lower() or needle in user["email"].lower()]
        return users

    def update_admin_user(self, user_id: str, payload: dict) -> dict:
        user = self._find_by_id(self.admin_users, user_id, "admin_user_not_found", "Admin user not found.")
        for key in ("role", "status", "scope"):
            if payload.get(key) is not None:
                user[key] = payload[key]
        user["is_internal_domain_compliant"] = self._make_compliance(user["role"], user["email"])
        user["last_active_at"] = utc_now_iso()
        return deepcopy(user)

    def list_role_policies(self, scenario: str) -> list[dict]:
        if scenario == "error":
            self._raise(500, "role_policy_fetch_failed", "Unable to load role policies.")
        if scenario == "empty":
            return []
        return deepcopy(self.role_policies)

    def list_system_settings(self, scenario: str) -> list[dict]:
        if scenario == "error":
            self._raise(500, "system_settings_fetch_failed", "Unable to load system settings.")
        if scenario == "empty":
            return []
        return deepcopy(self.system_settings)

    def update_system_setting(self, key: str, value: str) -> dict:
        for setting in self.system_settings:
            if setting["key"] == key:
                setting["value"] = value
                return deepcopy(setting)
        self._raise(404, "system_setting_not_found", "System setting not found.")

    def list_audit_logs(
        self,
        scenario: str,
        actor_role: str | None = None,
        action: str | None = None,
        target_type: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        if scenario == "error":
            self._raise(500, "audit_logs_fetch_failed", "Unable to load audit logs.")

        logs = deepcopy(self.dense_audit_logs if scenario == "dense-audit-history" else self.audit_logs)
        if scenario == "empty":
            logs = []
        if actor_role:
            logs = [log for log in logs if log["actor_role"] == actor_role]
        if action:
            logs = [log for log in logs if log["action"] == action]
        if target_type:
            logs = [log for log in logs if log["target_type"] == target_type]
        if search:
            needle = search.lower()
            logs = [
                log
                for log in logs
                if needle in log["actor_name"].lower()
                or needle in log["target_label"].lower()
                or needle in log["action"]
            ]
        return logs

    def list_conversations(self, scenario: str) -> list[dict]:
        if scenario == "empty":
            return []
        return deepcopy(self.conversations)

    def send_chat_message(self, payload: dict, scenario: str) -> dict:
        if scenario == "error":
            self._raise(500, "chat_failed", "Unable to generate assistant response.")

        question = payload.get("message") or "Can you clarify the request?"
        conversation_id = payload.get("conversationId") or "conv-001"
        reply = {
            "id": f"msg-{uuid4().hex[:8]}",
            "role": "assistant",
            "content": (
                f'Toi tim thay thong tin lien quan den: "{question}", nhung do tin cay dang thap va ban nen doi chieu them voi phong ban phu trach.'
                if scenario == "low-confidence"
                else f'Day la phan hoi tu /web backend cho cau hoi: "{question}". Assistant se uu tien tai lieu moi, co nguon va canh bao neu can.'
            ),
            "created_at": utc_now_iso(),
            "confidence": 0.35 if scenario == "low-confidence" else 0.86,
            "references": [
                {
                    "id": "ref-response-001",
                    "title": "Thong bao hoc phi hoc ky 2" if scenario == "low-confidence" else "Quy dinh hoc vu 2024-2025",
                    "href": "/documents/doc-002" if scenario == "low-confidence" else "/documents/doc-001",
                    "excerpt": "BFF mock reference excerpt used for frontend-backend contract alignment.",
                    "status_label": "Pending review" if scenario == "low-confidence" else "Approved",
                }
            ],
            "warnings": (
                [{"code": "low_confidence", "message": "Assistant confidence is low because metadata is incomplete."}]
                if scenario == "low-confidence"
                else []
            ),
        }
        for conversation in self.conversations:
            if conversation["id"] == conversation_id:
                conversation["messages"].append(
                    {
                        "id": f"msg-{uuid4().hex[:8]}",
                        "role": "user",
                        "content": question,
                        "created_at": utc_now_iso(),
                        "references": [],
                        "warnings": [],
                    }
                )
                conversation["messages"].append(deepcopy(reply))
                conversation["updated_at"] = reply["created_at"]
                break
        return {"conversation_id": conversation_id, "message": reply}

    def get_overview(self) -> dict:
        total_documents = len(self.documents)
        processing = len([document for document in self.documents if document["processing_status"] in {"uploading", "extracting", "indexing"}])
        failed = len([document for document in self.documents if document["processing_status"] == "failed"])
        pending = len([document for document in self.documents if document["lifecycle_status"] == "pending_review"])
        indexed = len([document for document in self.documents if document["processing_status"] == "completed"])
        return {
            "total_documents": total_documents,
            "indexed": indexed,
            "processing": processing,
            "failed": failed,
            "pending": pending,
            "lightrag_health": "mock-backed",
        }

    def get_pipeline_status(self) -> dict:
        active_jobs = [job for job in self.jobs if job["status"] not in {"completed", "failed"}]
        completed_jobs = [job for job in self.jobs if job["status"] == "completed"]
        last_processed = max((job["updated_at"] for job in completed_jobs), default=None)
        return {
            "is_processing": bool(active_jobs),
            "queue_size": len(active_jobs),
            "last_processed": last_processed,
            "error_message": None,
        }

    def get_graph_stats(self) -> dict:
        labels = sorted({tag for document in self.documents for tag in document["supplemental_metadata"]["tags"]})
        return {"total_labels": len(labels), "top_labels": labels[:20]}

    def get_health(self) -> dict:
        return {"admin_api": "healthy", "lightrag": "mock-backed", "lightrag_url": "in-memory://workspace-service"}
