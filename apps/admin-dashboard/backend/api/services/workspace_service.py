"""Repository-backed workspace service for the /web backend and its tests.

Replaces the old snapshot-based mutation pattern (_persist_state) with
per-entity CRUD calls on the WorkspaceStateStore, so each mutation writes
only the affected row(s) instead of the full state.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlparse
from typing import Any, cast
from uuid import uuid4

from api.clients.lightrag_client import get_lightrag_client, get_public_lightrag_client
from api.config import settings
from api.errors import ApiServiceError
from api.schemas import Role
from api.services.fixtures import INTERNAL_EMAIL_DOMAIN
from api.services.workspace_store import WorkspaceStateStore

INTERNAL_ROLES = {"teacher", "admin"}
DOCUMENT_ADMIN_ROLES = {"admin"}
PUBLIC_DOCUMENT_ROLES = {"guest", "student", "teacher"}
REDACTED_LABEL = "Da an trong giao dien cong khai"
REDACTED_EMAIL = REDACTED_LABEL
PUBLIC_WORKSPACE_SOURCE_PREFIX = "admin-dashboard-public://"


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_avatar_initials(name: str, email: str) -> str:
    tokens = [token for token in name.replace("-", " ").split() if token]
    if len(tokens) >= 2:
        return f"{tokens[0][0]}{tokens[-1][0]}".upper()
    if tokens:
        return tokens[0][:2].upper()
    return email[:2].upper()


class InMemoryWorkspaceService:
    """Provides contract-aligned data via per-entity store CRUD."""

    def __init__(self, store: WorkspaceStateStore | None = None) -> None:
        if store is None:
            raise ValueError("A workspace store must be provided.")
        self.store = store
        self._public_workspace_seeded = False

    def reset(self) -> None:
        self.store.reset()
        self._public_workspace_seeded = False

    def _raise(self, status_code: int, code: str, message: str, details: Any = None) -> None:
        raise ApiServiceError(status_code=status_code, code=code, message=message, details=details)

    def _find_by_id(self, items: list[dict], item_id: str, error_code: str, message: str) -> dict:
        for item in items:
            if item["id"] == item_id:
                return item
        self._raise(404, error_code, message)

    def _actor(self, role: Role) -> dict:
        sessions = self.store.get_session_templates()
        return deepcopy(sessions[role]["user"])

    def _make_compliance(self, role: str, email: str) -> bool:
        return role not in INTERNAL_ROLES or email.lower().endswith(INTERNAL_EMAIL_DOMAIN)

    def _default_scope_for_role(self, role: Role) -> str:
        if role == "student":
            return "student_portal"
        if role == "teacher":
            return "teacher_workspace"
        return "admin_console"

    def _find_admin_user_by_email(self, email: str) -> dict | None:
        return self.store.get_admin_user_by_email(email)

    def _build_named_session(
        self,
        *,
        role: Role,
        email: str,
        name: str,
        session_id: str | None = None,
    ) -> dict:
        sessions = self.store.get_session_templates()
        session = deepcopy(sessions[role])
        session["session_id"] = session_id or f"session-{uuid4().hex[:8]}"
        session["status"] = "authenticated"
        session["user"]["id"] = f"user-{sha256(email.lower().encode()).hexdigest()[:12]}"
        session["user"]["name"] = name
        session["user"]["email"] = email.lower()
        session["user"]["avatar_initials"] = make_avatar_initials(name, email)
        if role == "student":
            session["user"]["department"] = "Sinh vien UIT"
        elif role == "teacher":
            session["user"]["department"] = "Giang vien UIT"
        else:
            session["user"]["department"] = "Quan tri he thong"
        return session

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

    def _is_document_admin(self, role: Role) -> bool:
        return role in DOCUMENT_ADMIN_ROLES

    def _should_limit_document_catalog(self, role: Role) -> bool:
        return role in PUBLIC_DOCUMENT_ROLES

    def _redact_document_for_public_surface(self, document: dict) -> dict:
        redacted = deepcopy(document)
        issuing_unit = redacted["supplemental_metadata"]["issuing_unit"]

        redacted["owner_name"] = issuing_unit
        redacted["owner_email"] = REDACTED_EMAIL
        redacted["system_metadata"]["file_source"] = REDACTED_LABEL
        redacted["system_metadata"]["content_hash"] = REDACTED_LABEL

        if redacted.get("traceability"):
            redacted["traceability"]["source_submission_id"] = None
            redacted["traceability"]["source_review_id"] = None
            redacted["traceability"]["reviewed_by_name"] = None

        for version in redacted.get("version_history", []):
            version["file_source"] = REDACTED_LABEL
            version["content_hash"] = REDACTED_LABEL
            version["source_submission_id"] = None
            version["source_review_id"] = None

        redacted["activity_history"] = []
        return redacted

    def _extract_document_id_from_href(self, href: str) -> str | None:
        path = urlparse(href).path if href else ""
        if not path.startswith("/documents/"):
            return None
        _, _, document_id = path.partition("/documents/")
        return document_id or None

    def _find_document_fixture(self, document_id: str | None) -> dict | None:
        if not document_id:
            return None
        return self.store.get_document_by_id(document_id)

    def _redact_reference_for_public_surface(self, reference: dict) -> dict:
        redacted = deepcopy(reference)
        document = self._find_document_fixture(self._extract_document_id_from_href(reference.get("href", "")))
        if document is None:
            return redacted

        if (
            document["supplemental_metadata"]["visibility_scope"] != "public"
            or document["lifecycle_status"] not in {"approved", "archived"}
        ):
            redacted["title"] = "Tai lieu dang cho kiem duyet noi bo"
            redacted["excerpt"] = "Chi tiet nguon da duoc an trong giao dien cong khai."

        return redacted

    def _redact_conversation_for_public_surface(self, conversation: dict) -> dict:
        redacted = deepcopy(conversation)
        for message in redacted.get("messages", []):
            message["references"] = [
                self._redact_reference_for_public_surface(reference) for reference in message.get("references", [])
            ]
        return redacted

    # ── Session / Auth ──

    def get_session(self, role: Role, scenario: str) -> dict:
        if scenario == "auth-error":
            self._raise(500, "auth_fetch_failed", "Unable to validate the current session.")
        if scenario == "forbidden":
            self._raise(403, "forbidden", "Access denied for this mock scenario.")

        sessions = self.store.get_session_templates()
        session = deepcopy(sessions[role])
        if scenario == "non-compliant-internal-email" and role in INTERNAL_ROLES:
            session["user"]["email"] = f"{role}@uit.edu.vn"
        return session

    def issue_session_token(self, role: Role, auth_method: str = "demo_bootstrap", session: dict | None = None) -> str:
        token = f"uit-session-{uuid4().hex}"
        stored_session = deepcopy(session) if session is not None else None
        self.store.create_issued_session_token(token, {"role": role, "auth_method": auth_method, "session": stored_session})
        return token

    def resolve_session_role(self, token: str | None) -> Role | None:
        if not token:
            return None
        session = self.store.get_issued_session_token(token)
        if session is None:
            return None
        if isinstance(session, str):
            return session
        stored_session = session.get("session")
        if isinstance(stored_session, dict):
            role = stored_session.get("user", {}).get("role")
            return role if role in {"guest", "student", "teacher", "admin"} else None
        role = session.get("role")
        return role if role in {"guest", "student", "teacher", "admin"} else None

    def resolve_session(self, token: str | None, scenario: str) -> dict | None:
        if not token:
            return None

        stored = self.store.get_issued_session_token(token)
        if stored is None:
            return None
        if isinstance(stored, str):
            return self.get_session(stored, scenario)

        stored_session = stored.get("session")
        if isinstance(stored_session, dict):
            return deepcopy(stored_session)

        role = stored.get("role")
        if role in {"guest", "student", "teacher", "admin"}:
            return self.get_session(role, scenario)
        return None

    def revoke_session_token(self, token: str | None) -> None:
        if token:
            self.store.delete_issued_session_token(token)

    def issue_sso_state(self, return_to: str | None, scenario: str = "happy") -> str:
        state = f"sso-{uuid4().hex}"
        payload = {
            "return_to": return_to or "",
            "scenario": scenario,
            "created_at": utc_now_iso(),
        }
        self.store.upsert_pending_sso_state(state, payload)
        return state

    def read_sso_state(self, state: str) -> dict[str, str] | None:
        pending = self.store.get_pending_sso_states()
        stored = pending.get(state)
        return deepcopy(stored) if stored else None

    def consume_sso_state(self, state: str) -> dict[str, str] | None:
        stored = self.store.consume_pending_sso_state(state)
        return deepcopy(stored) if stored else None

    def resolve_or_create_google_user(self, email: str, name: str) -> dict:
        normalized_email = email.strip().lower()
        user = self._find_admin_user_by_email(normalized_email)
        now = utc_now_iso()

        if user is None:
            user = {
                "id": f"usr-{uuid4().hex[:8]}",
                "name": name,
                "email": normalized_email,
                "role": "student",
                "status": "active",
                "scope": "student_portal",
                "last_active_at": now,
                "is_internal_domain_compliant": True,
            }
            self.store.upsert_admin_user(user)
            return deepcopy(user)

        user["name"] = name or user["name"]
        user["last_active_at"] = now
        user["is_internal_domain_compliant"] = self._make_compliance(user["role"], user["email"])
        self.store.upsert_admin_user(user)
        return deepcopy(user)

    def build_google_sso_session(self, email: str, name: str) -> tuple[Role, dict]:
        user = self.resolve_or_create_google_user(email, name)
        role = cast(Role, user["role"])
        session = self._build_named_session(
            role=role,
            email=user["email"],
            name=user["name"],
        )
        return role, session

    # ── Documents ──

    def list_documents(
        self,
        scenario: str,
        role: Role = "guest",
        search: str | None = None,
        lifecycle_status: str | None = None,
        visibility_scope: str | None = None,
    ) -> list[dict]:
        if scenario == "error":
            self._raise(500, "document_fetch_failed", "Unable to load document library.")

        documents = self.store.list_all_documents()
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
        if self._should_limit_document_catalog(role):
            documents = [
                document
                for document in documents
                if document["supplemental_metadata"]["visibility_scope"] == "public"
                and document["lifecycle_status"] in {"approved", "archived"}
            ]

        if self._is_document_admin(role):
            return documents

        return [self._redact_document_for_public_surface(document) for document in documents]

    def get_document(self, document_id: str, scenario: str, role: Role = "guest") -> dict:
        document = self.store.get_document_by_id(document_id)
        if document is None:
            self._raise(404, "document_not_found", "Document not found.")
        if self._is_document_admin(role):
            return document
        return self._redact_document_for_public_surface(document)

    def archive_document(self, document_id: str, actor_role: Role) -> dict:
        document = self.store.get_document_by_id(document_id)
        if document is None:
            self._raise(404, "document_not_found", "Document not found.")

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
        self.store.create_audit_log(audit_entry)
        document.setdefault("activity_history", []).insert(0, deepcopy(audit_entry))
        self.store.update_document_payload(document_id, document)
        self._remove_public_workspace_document(document_id)
        return deepcopy(document)

    def reindex_document(self, document_id: str, actor_role: Role) -> dict:
        document = self.store.get_document_by_id(document_id)
        if document is None:
            self._raise(404, "document_not_found", "Document not found.")

        now = utc_now_iso()
        document["processing_status"] = "indexing"
        document["updated_at"] = now
        job = {
            "id": f"job-{uuid4().hex[:8]}",
            "type": "indexing",
            "status": "indexing",
            "progress": 12,
            "related_title": document["title"],
            "started_at": now,
            "updated_at": now,
            "message": "Reindex triggered from document action.",
        }
        self.store.create_job(job)
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
        self.store.create_audit_log(audit_entry)
        document.setdefault("activity_history", []).insert(0, deepcopy(audit_entry))
        self.store.update_document_payload(document_id, document)
        self._reconcile_document_public_workspace(document)
        return deepcopy(document)

    # ── Submissions ──

    def list_submissions(self, scenario: str, lifecycle_status: str | None = None) -> list[dict]:
        submissions = self.store.list_all_submissions()
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
        self.store.create_submission(submission)
        job = {
            "id": f"job-{uuid4().hex[:8]}",
            "type": "upload",
            "status": "uploading",
            "progress": 15,
            "related_title": title,
            "started_at": now,
            "updated_at": now,
            "message": "Submission accepted by the /web BFF and queued for extraction.",
        }
        self.store.create_job(job)
        actor = self._actor(actor_role)
        review = {
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
        }
        self.store.create_review(review)
        audit_entry = {
            "id": f"audit-{uuid4().hex[:8]}",
            "actor_name": actor["name"],
            "actor_role": actor_role,
            "action": "upload_submission",
            "target_type": "submission",
            "target_id": submission["id"],
            "target_label": submission["title"],
            "created_at": now,
        }
        self.store.create_audit_log(audit_entry)
        return deepcopy(submission)

    def mark_submission_ingestion_started(self, submission_id: str, ingest_result: dict) -> dict:
        submission = self.store.get_submission_by_id(submission_id)
        if submission is None:
            self._raise(404, "submission_not_found", "Submission not found.")

        now = utc_now_iso()
        track_id = str(ingest_result.get("track_id") or ingest_result.get("id") or "").strip()
        source = str(ingest_result.get("source") or "live-ingestion")
        status = str(ingest_result.get("status") or "queued")

        submission["processing_status"] = "indexing"
        submission["updated_at"] = now
        self.store.update_submission_payload(submission_id, submission)

        job = self._find_submission_upload_job(submission)
        if job is not None:
            job["status"] = "indexing"
            job["progress"] = 35
            job["updated_at"] = now
            job["message"] = f"Ingestion accepted by {source} with status '{status}'."
            if track_id:
                job["message"] += f" Track ID: {track_id}."
            self.store.update_job_payload(job["id"], job)

        return deepcopy(submission)

    def mark_submission_ingestion_failed(self, submission_id: str, error_message: str) -> dict:
        submission = self.store.get_submission_by_id(submission_id)
        if submission is None:
            self._raise(404, "submission_not_found", "Submission not found.")

        now = utc_now_iso()
        submission["processing_status"] = "failed"
        submission["updated_at"] = now
        self.store.update_submission_payload(submission_id, submission)

        job = self._find_submission_upload_job(submission)
        if job is not None:
            job["status"] = "failed"
            job["progress"] = 100
            job["updated_at"] = now
            job["message"] = error_message
            self.store.update_job_payload(job["id"], job)

        return deepcopy(submission)

    # ── Reviews ──

    def list_reviews(self, scenario: str, status: str | None = None) -> list[dict]:
        reviews = self.store.list_all_reviews()
        if scenario == "empty":
            reviews = []
        if status:
            reviews = [review for review in reviews if review["status"] == status]
        return reviews

    def apply_review_decision(self, review_id: str, payload: dict, actor_role: Role) -> dict:
        review = self.store.get_review_by_id(review_id)
        if review is None:
            self._raise(404, "review_not_found", "Review task not found.")

        submission = self.store.get_submission_by_id(review["submission_id"])
        if submission is None:
            self._raise(404, "submission_not_found", "Submission linked to this review was not found.")

        next_status = payload["status"]
        now = utc_now_iso()
        previous_published_document_id = review.get("published_document_id")
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
            document = self.store.get_document_by_id(published_document_id)
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
                self.store.update_document_payload(published_document_id, document_payload)
            else:
                self.store.create_document(document_payload)
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
        self.store.create_audit_log(audit_entry)
        if next_status == "approved" and review.get("published_document_id"):
            published_document = self.store.get_document_by_id(review["published_document_id"])
            if published_document:
                published_document.setdefault("activity_history", []).insert(0, deepcopy(audit_entry))
                self.store.update_document_payload(review["published_document_id"], published_document)
                self._reconcile_document_public_workspace(published_document)
        elif previous_published_document_id:
            self._remove_public_workspace_document(previous_published_document_id)
        self.store.update_review_payload(review_id, review)
        self.store.update_submission_payload(submission["id"], submission)
        return deepcopy(review)

    # ── Jobs ──

    def _find_submission_upload_job(self, submission: dict) -> dict | None:
        for job in self.store.list_all_jobs():
            if (
                job["type"] == "upload"
                and job["related_title"] == submission["title"]
                and job["started_at"] == submission["created_at"]
            ):
                return job
        return None

    def list_jobs(self, scenario: str, status: str | None = None, job_type: str | None = None) -> list[dict]:
        jobs = self.store.list_all_jobs()
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
        job = self.store.get_job_by_id(job_id)
        if job is None:
            self._raise(404, "job_not_found", "Job not found.")
        job["status"] = "indexing"
        job["progress"] = 15
        job["updated_at"] = utc_now_iso()
        job["message"] = "Retry accepted by the /web BFF."
        self.store.update_job_payload(job_id, job)
        return deepcopy(job)

    # ── Admin users ──

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

        users = self.store.list_all_admin_users()
        if scenario == "empty":
            users = []
        elif scenario == "non-compliant-internal-email":
            for user in users:
                if user["id"] == "usr-005":
                    user["email"] = "pending-teacher@gmail.com"
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
        user = self.store.get_admin_user_by_id(user_id)
        if user is None:
            self._raise(404, "admin_user_not_found", "Admin user not found.")
        for key in ("role", "status", "scope"):
            if payload.get(key) is not None:
                user[key] = payload[key]
        if payload.get("role") is not None and payload.get("scope") is None:
            user["scope"] = self._default_scope_for_role(user["role"])
        user["is_internal_domain_compliant"] = self._make_compliance(user["role"], user["email"])
        user["last_active_at"] = utc_now_iso()
        self.store.update_admin_user_payload(user_id, user)
        return deepcopy(user)

    # ── Role policies / System settings ──

    def list_role_policies(self, scenario: str) -> list[dict]:
        if scenario == "error":
            self._raise(500, "role_policy_fetch_failed", "Unable to load role policies.")
        if scenario == "empty":
            return []
        return self.store.list_all_role_policies()

    def list_system_settings(self, scenario: str) -> list[dict]:
        if scenario == "error":
            self._raise(500, "system_settings_fetch_failed", "Unable to load system settings.")
        if scenario == "empty":
            return []
        return self.store.list_all_system_settings()

    def update_system_setting(self, key: str, value: str) -> dict:
        updated = self.store.update_system_setting_value(key, value)
        if updated is None:
            self._raise(404, "system_setting_not_found", "System setting not found.")
        return deepcopy(updated)

    # ── Audit logs ──

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

        logs = self.store.list_all_dense_audit_logs() if scenario == "dense-audit-history" else self.store.list_all_audit_logs()
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

    # ── Conversations / Chat ──

    def list_conversations(self, scenario: str, role: Role = "guest") -> list[dict]:
        if scenario == "empty":
            return []
        conversations = self.store.list_all_conversations()
        if self._is_document_admin(role):
            return conversations
        return [self._redact_conversation_for_public_surface(conversation) for conversation in conversations]

    def _build_mock_chat_reply(self, question: str, scenario: str) -> dict:
        return {
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

    def _normalize_chat_text(self, value: str | None) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()

    def _normalize_chat_tokens(self, value: str | None) -> list[str]:
        return [token for token in self._normalize_chat_text(value).split() if len(token) >= 2]

    def _list_public_chat_documents(self) -> list[dict]:
        return [
            document
            for document in self.store.list_all_documents()
            if document["supplemental_metadata"]["visibility_scope"] == "public"
            and document["lifecycle_status"] in {"approved", "archived"}
        ]

    def _score_public_document_for_chat(self, document: dict, question: str) -> float:
        question_text = self._normalize_chat_text(question)
        question_tokens = self._normalize_chat_tokens(question)
        if not question_tokens:
            return 0.0

        title = self._normalize_chat_text(document["title"])
        tags = [self._normalize_chat_text(tag) for tag in document["supplemental_metadata"].get("tags", [])]
        tags_joined = " ".join(tags)
        issuing_unit = self._normalize_chat_text(document["supplemental_metadata"].get("issuing_unit"))
        notes = self._normalize_chat_text(document["supplemental_metadata"].get("notes"))
        temporal_metadata = document.get("temporal_metadata", {})
        document_number = self._normalize_chat_text(temporal_metadata.get("document_number"))
        academic_year = self._normalize_chat_text(temporal_metadata.get("academic_year"))
        cohort_years = {str(year) for year in temporal_metadata.get("cohort_years", [])}

        score = 0.0
        for token in question_tokens:
            if token in title:
                score += 2.5
            if token in tags_joined:
                score += 2.0
            if token in document_number:
                score += 2.5
            if token in academic_year:
                score += 1.8
            if token in issuing_unit:
                score += 0.8
            if token in notes:
                score += 0.6
            if token in cohort_years:
                score += 1.6

        phrase_weights = {
            "hoc phi": 4.0,
            "hoc vu": 4.0,
            "hoc bong": 4.0,
            "dang ky mon hoc": 5.0,
            "lich dang ky": 4.5,
            "quy dinh": 3.5,
            "thong bao": 2.0,
        }
        combined_text = " ".join(filter(None, [title, tags_joined, notes, issuing_unit, document_number, academic_year]))
        for phrase, weight in phrase_weights.items():
            if phrase in question_text and phrase in combined_text:
                score += weight

        if temporal_metadata.get("academic_year") and academic_year and academic_year in question_text:
            score += 2.5

        if document["lifecycle_status"] == "archived":
            score -= 1.0

        return max(score, 0.0)

    def _build_public_reference_excerpt(self, document: dict) -> str:
        temporal_metadata = document.get("temporal_metadata", {})
        document_number = temporal_metadata.get("document_number")
        valid_from = temporal_metadata.get("valid_from")
        valid_until = temporal_metadata.get("valid_until")
        notes = str(document["supplemental_metadata"].get("notes") or "").strip()

        parts: list[str] = []
        if document_number:
            parts.append(str(document_number))
        if valid_from and valid_until:
            parts.append(f"Hieu luc tu {valid_from} den {valid_until}.")
        elif valid_from:
            parts.append(f"Co thong tin hieu luc tu {valid_from}.")
        if notes:
            parts.append(notes)
        return " ".join(parts).strip() or "Tai lieu cong khai duoc phe duyet cho tra cuu tren UIT AI."

    def _build_public_reference(self, document: dict) -> dict:
        return {
            "id": f"ref-public-{document['id']}",
            "title": document["title"],
            "href": f"/documents/{document['id']}",
            "excerpt": self._build_public_reference_excerpt(document),
            "status_label": self._status_label_for_reference_document(document),
        }

    def _public_workspace_source(self, document_id: str) -> str:
        return f"{PUBLIC_WORKSPACE_SOURCE_PREFIX}{document_id}"

    def _extract_document_id_from_public_source(self, file_path: str) -> str | None:
        normalized = str(file_path or "").strip()
        if normalized.startswith(PUBLIC_WORKSPACE_SOURCE_PREFIX):
            return normalized.removeprefix(PUBLIC_WORKSPACE_SOURCE_PREFIX).strip() or None
        return None

    def _should_sync_document_to_public_workspace(self, document: dict) -> bool:
        return (
            document.get("lifecycle_status") == "approved"
            and document.get("supplemental_metadata", {}).get("visibility_scope") == "public"
            and not document.get("system_metadata", {}).get("is_archived", False)
        )

    def _build_public_workspace_document_text(self, document: dict) -> str:
        temporal_metadata = document.get("temporal_metadata", {})
        supplemental_metadata = document.get("supplemental_metadata", {})
        traceability = document.get("traceability", {})
        lines = [
            f"Tieu de: {document['title']}",
            f"Trang thai cong bo: {document.get('lifecycle_status')}",
            f"Pham vi hien thi: {supplemental_metadata.get('visibility_scope')}",
        ]
        document_number = temporal_metadata.get("document_number")
        if document_number:
            lines.append(f"So hieu: {document_number}")
        issuing_unit = supplemental_metadata.get("issuing_unit")
        if issuing_unit:
            lines.append(f"Don vi ban hanh: {issuing_unit}")
        academic_year = temporal_metadata.get("academic_year")
        if academic_year:
            lines.append(f"Nam hoc: {academic_year}")
        valid_from = temporal_metadata.get("valid_from")
        valid_until = temporal_metadata.get("valid_until")
        if valid_from and valid_until:
            lines.append(f"Hieu luc: tu {valid_from} den {valid_until}")
        elif valid_from:
            lines.append(f"Hieu luc: tu {valid_from}")
        cohort_years = temporal_metadata.get("cohort_years") or []
        if cohort_years:
            lines.append(f"Cac khoa lien quan: {', '.join(cohort_years)}")
        tags = supplemental_metadata.get("tags") or []
        if tags:
            lines.append(f"Nhan: {', '.join(tags)}")
        notes = str(supplemental_metadata.get("notes") or "").strip()
        if notes:
            lines.append(f"Ghi chu cong khai: {notes}")
        publication_reason = str(traceability.get("publication_reason") or "").strip()
        if publication_reason:
            lines.append(f"Ly do cong bo: {publication_reason}")
        return "\n".join(lines)

    def _sync_public_workspace_document(self, document: dict) -> dict:
        if not settings.LIVE_INGESTION_MODE or not settings.LIGHTRAG_PUBLIC_URL:
            return {"status": "skipped", "source": "public-live-disabled"}

        client = get_public_lightrag_client()
        file_source = self._public_workspace_source(document["id"])
        existing_ids = client.find_document_ids_by_file_path(file_source)
        if existing_ids:
            client.delete_document(existing_ids)

        result = client.insert_text(
            self._build_public_workspace_document_text(document),
            source=file_source,
        )
        if result.get("error"):
            self._public_workspace_seeded = False
            return {"status": "error", "source": "lightrag-public", "raw": result}
        return {"status": "accepted", "source": "lightrag-public", "raw": result}

    def _remove_public_workspace_document(self, document_id: str) -> dict:
        if not settings.LIVE_INGESTION_MODE or not settings.LIGHTRAG_PUBLIC_URL:
            return {"status": "skipped", "source": "public-live-disabled"}

        client = get_public_lightrag_client()
        existing_ids = client.find_document_ids_by_file_path(self._public_workspace_source(document_id))
        if not existing_ids:
            return {"status": "not_found", "source": "lightrag-public"}
        result = client.delete_document(existing_ids)
        if result.get("error"):
            self._public_workspace_seeded = False
            return {"status": "error", "source": "lightrag-public", "raw": result}
        return {"status": "deleted", "source": "lightrag-public", "raw": result}

    def _ensure_public_workspace_seeded(self) -> None:
        if self._public_workspace_seeded:
            return
        if not settings.LIVE_INGESTION_MODE or not settings.LIGHTRAG_PUBLIC_URL:
            return

        synced_ok = True
        for document in self.store.list_all_documents():
            try:
                if self._should_sync_document_to_public_workspace(document):
                    result = self._sync_public_workspace_document(document)
                else:
                    result = self._remove_public_workspace_document(document["id"])
                if result.get("status") == "error":
                    synced_ok = False
            except Exception:
                synced_ok = False
        self._public_workspace_seeded = synced_ok

    def _reconcile_document_public_workspace(self, document: dict | None) -> dict:
        if document is None:
            return {"status": "skipped", "source": "missing-document"}
        if self._should_sync_document_to_public_workspace(document):
            return self._sync_public_workspace_document(document)
        return self._remove_public_workspace_document(document["id"])

    def _build_public_catalog_chat_reply(self, question: str) -> dict:
        matches = sorted(
            (
                {
                    "document": document,
                    "score": self._score_public_document_for_chat(document, question),
                }
                for document in self._list_public_chat_documents()
            ),
            key=lambda item: item["score"],
            reverse=True,
        )

        strong_matches = [item for item in matches if item["score"] >= 3.0]
        if not strong_matches:
            return {
                "id": f"msg-{uuid4().hex[:8]}",
                "role": "assistant",
                "content": (
                    "Toi chua tim thay tai lieu cong khai phu hop trong he thong de tra loi cau hoi nay. "
                    "Ban nen neu ro hon chu de hoac doi chieu them voi don vi phu trach cua UIT."
                ),
                "created_at": utc_now_iso(),
                "confidence": 0.28,
                "references": [],
                "warnings": [
                    {
                        "code": "low_confidence",
                        "message": "Khong tim thay tai lieu cong khai co do phu hop du cao de dua ra cau tra loi co nguon.",
                    }
                ],
            }

        top_match = strong_matches[0]["document"]
        temporal_metadata = top_match.get("temporal_metadata", {})
        document_number = temporal_metadata.get("document_number")
        academic_year = temporal_metadata.get("academic_year")
        valid_from = temporal_metadata.get("valid_from")
        valid_until = temporal_metadata.get("valid_until")
        cohort_years = temporal_metadata.get("cohort_years") or []

        summary_parts = [f'Tai lieu cong khai phu hop nhat hien tai la "{top_match["title"]}"']
        if document_number:
            summary_parts[-1] += f" ({document_number})"
        summary_parts[-1] += "."
        if valid_from and valid_until:
            summary_parts.append(f"Tai lieu nay co hieu luc tu {valid_from} den {valid_until}.")
        elif valid_from:
            summary_parts.append(f"Tai lieu nay ghi nhan moc ap dung tu {valid_from}.")
        if academic_year:
            summary_parts.append(f"Du lieu dang gan voi nam hoc {academic_year}.")
        if cohort_years:
            summary_parts.append(f"Cac khoa duoc de cap gom {', '.join(cohort_years)}.")
        notes = str(top_match["supplemental_metadata"].get("notes") or "").strip()
        if notes:
            summary_parts.append(notes)
        if top_match["lifecycle_status"] == "archived":
            summary_parts.append("Day la tai lieu luu tru, ban nen doi chieu them voi thong bao moi nhat neu can xac nhan.")

        warnings: list[dict] = []
        confidence = 0.76
        if top_match["lifecycle_status"] == "archived":
            confidence = 0.44
            warnings.append(
                {
                    "code": "archived_source",
                    "message": "Nguon tham chieu chinh la tai lieu da luu tru, co the khong con la huong dan moi nhat.",
                }
            )
        elif strong_matches[0]["score"] < 5.0:
            confidence = 0.58
            warnings.append(
                {
                    "code": "low_confidence",
                    "message": "Da tim thay tai lieu cong khai lien quan, nhung ban nen doi chieu them voi phong ban phu trach.",
                }
            )

        references = [self._build_public_reference(item["document"]) for item in strong_matches[:2]]
        return {
            "id": f"msg-{uuid4().hex[:8]}",
            "role": "assistant",
            "content": " ".join(summary_parts),
            "created_at": utc_now_iso(),
            "confidence": confidence,
            "references": references,
            "warnings": warnings,
        }

    def _should_use_live_chat(self, role: Role, scenario: str) -> bool:
        return settings.LIVE_INGESTION_MODE and role in {"teacher", "admin"} and scenario == "happy"

    def _should_use_public_live_chat(self, role: Role, scenario: str) -> bool:
        return (
            settings.LIVE_INGESTION_MODE
            and bool(settings.LIGHTRAG_PUBLIC_URL)
            and role in {"guest", "student"}
            and scenario == "happy"
        )

    def _should_use_public_catalog_chat(self, role: Role, scenario: str) -> bool:
        return role in {"guest", "student"} and scenario == "happy"

    def _build_chat_conversation_history(self, conversation: dict | None) -> list[dict] | None:
        if conversation is None:
            return None
        history: list[dict] = []
        for message in conversation.get("messages", [])[-6:]:
            role = str(message.get("role") or "").strip()
            content = str(message.get("content") or "").strip()
            if role in {"user", "assistant", "system"} and content:
                history.append({"role": role, "content": content})
        return history or None

    def _find_document_for_reference(self, file_path: str) -> dict | None:
        if not file_path:
            return None
        public_document_id = self._extract_document_id_from_public_source(file_path)
        if public_document_id:
            return self.store.get_document_by_id(public_document_id)
        file_name = Path(file_path).name.lower()
        file_stem = Path(file_path).stem.lower()
        for document in self.store.list_all_documents():
            source_name = Path(str(document["system_metadata"]["file_source"])).name.lower()
            title = str(document["title"]).lower()
            if file_name and source_name == file_name:
                return document
            if file_stem and (file_stem == title or file_stem in source_name):
                return document
        return None

    def _status_label_for_reference_document(self, document: dict | None) -> str:
        if document is None:
            return "Indexed"
        lifecycle_status = document.get("lifecycle_status")
        if lifecycle_status == "approved":
            return "Approved"
        if lifecycle_status == "archived":
            return "Archived"
        return "Pending review"

    def _build_live_reference(self, reference: dict) -> dict:
        document = self._find_document_for_reference(str(reference.get("file_path") or ""))
        if document is not None:
            return {
                "id": str(reference.get("reference_id") or f"ref-{uuid4().hex[:8]}"),
                "title": document["title"],
                "href": f"/documents/{document['id']}",
                "excerpt": "Nguon duoc truy xuat tu co so tri thuc LightRAG va da duoc map ve tai lieu noi bo.",
                "status_label": self._status_label_for_reference_document(document),
            }
        return {
            "id": str(reference.get("reference_id") or f"ref-{uuid4().hex[:8]}"),
            "title": "Nguon tai lieu he thong",
            "href": "/documents",
            "excerpt": "Nguon duoc tra ve tu truy van LightRAG.",
            "status_label": "Indexed",
        }

    def _build_public_live_reference(self, reference: dict) -> dict:
        document = self._find_document_for_reference(str(reference.get("file_path") or ""))
        if document is not None:
            return {
                "id": str(reference.get("reference_id") or f"ref-{uuid4().hex[:8]}"),
                "title": document["title"],
                "href": f"/documents/{document['id']}",
                "excerpt": self._build_public_reference_excerpt(document),
                "status_label": self._status_label_for_reference_document(document),
            }
        return {
            "id": str(reference.get("reference_id") or f"ref-{uuid4().hex[:8]}"),
            "title": "Tai lieu cong khai UIT",
            "href": "/documents",
            "excerpt": "Nguon duoc tra ve tu khong gian tri thuc cong khai cua UIT AI.",
            "status_label": "Approved",
        }

    def _build_live_chat_reply(self, question: str, conversation: dict | None) -> dict:
        result = get_lightrag_client().query_text(
            question,
            conversation_history=self._build_chat_conversation_history(conversation),
            mode="mix",
            include_references=True,
            include_chunk_content=False,
            response_type="Multiple Paragraphs",
        )
        if result.get("error"):
            self._raise(502, "lightrag_query_failed", "Live chat query failed while generating the answer.")

        raw_response = str(result.get("response") or "").strip()
        references = [self._build_live_reference(reference) for reference in result.get("references") or []]
        no_context = "no relevant context found" in raw_response.lower() or not raw_response
        return {
            "id": f"msg-{uuid4().hex[:8]}",
            "role": "assistant",
            "content": (
                "Toi chua tim thay ngu canh phu hop trong kho tri thuc hien tai. Ban nen dien dat cu the hon hoac doi chieu voi don vi phu trach."
                if no_context
                else raw_response
            ),
            "created_at": utc_now_iso(),
            "confidence": 0.34 if no_context or not references else 0.82,
            "references": references,
            "warnings": (
                [{"code": "low_confidence", "message": "Assistant confidence is low because the live retrieval did not return grounded references."}]
                if no_context or not references
                else []
            ),
        }

    def _build_public_live_chat_reply(self, question: str, conversation: dict | None) -> dict:
        self._ensure_public_workspace_seeded()
        result = get_public_lightrag_client().query_text(
            question,
            conversation_history=self._build_chat_conversation_history(conversation),
            mode="mix",
            include_references=True,
            include_chunk_content=False,
            response_type="Multiple Paragraphs",
        )
        if result.get("error"):
            return self._build_public_catalog_chat_reply(question)

        raw_response = str(result.get("response") or "").strip()
        references = [self._build_public_live_reference(reference) for reference in result.get("references") or []]
        no_context = "no relevant context found" in raw_response.lower() or not raw_response
        if no_context or not references:
            return self._build_public_catalog_chat_reply(question)

        return {
            "id": f"msg-{uuid4().hex[:8]}",
            "role": "assistant",
            "content": raw_response,
            "created_at": utc_now_iso(),
            "confidence": 0.8,
            "references": references,
            "warnings": [],
        }

    def _get_lightrag_health_snapshot(self) -> dict:
        if not settings.LIVE_INGESTION_MODE:
            return {"status": "mock-backed", "url": "in-memory://workspace-service"}

        try:
            health = get_lightrag_client().health()
        except Exception:
            return {"status": "unreachable", "url": settings.LIGHTRAG_URL}

        if isinstance(health, dict):
            status = str(health.get("status") or "healthy")
            url = str(health.get("url") or settings.LIGHTRAG_URL)
            return {"status": status, "url": url}
        return {"status": "healthy", "url": settings.LIGHTRAG_URL}

    def _upsert_chat_conversation(self, conversation_id: str, question: str, reply: dict, existing_conversation: dict | None) -> None:
        user_message = {
            "id": f"msg-{uuid4().hex[:8]}",
            "role": "user",
            "content": question,
            "created_at": utc_now_iso(),
            "references": [],
            "warnings": [],
        }
        if existing_conversation is not None:
            updated_conversation = deepcopy(existing_conversation)
            updated_conversation["messages"].append(user_message)
            updated_conversation["messages"].append(deepcopy(reply))
            updated_conversation["updated_at"] = reply["created_at"]
            self.store.upsert_conversation(updated_conversation)
            return

        self.store.upsert_conversation(
            {
                "id": conversation_id,
                "title": question[:64] or "Cuoc tro chuyen moi",
                "updated_at": reply["created_at"],
                "messages": [user_message, deepcopy(reply)],
            }
        )

    def send_chat_message(self, payload: dict, scenario: str, role: Role = "guest") -> dict:
        if scenario == "error":
            self._raise(500, "chat_failed", "Unable to generate assistant response.")

        question = payload.get("message") or "Can you clarify the request?"
        conversation_id = payload.get("conversationId") or f"conv-{uuid4().hex[:8]}"
        existing_conversation = self.store.get_conversation_by_id(conversation_id)
        if self._should_use_live_chat(role, scenario):
            reply = self._build_live_chat_reply(question, existing_conversation)
        elif self._should_use_public_live_chat(role, scenario):
            reply = self._build_public_live_chat_reply(question, existing_conversation)
        elif self._should_use_public_catalog_chat(role, scenario):
            reply = self._build_public_catalog_chat_reply(question)
        else:
            reply = self._build_mock_chat_reply(question, scenario)
        self._upsert_chat_conversation(conversation_id, question, reply, existing_conversation)
        if self._is_document_admin(role):
            return {"conversation_id": conversation_id, "message": reply}
        return {
            "conversation_id": conversation_id,
            "message": {
                **reply,
                "references": [
                    self._redact_reference_for_public_surface(reference) for reference in reply.get("references", [])
                ],
            },
        }

    # ── Analytics ──

    def get_overview(self) -> dict:
        documents = self.store.list_all_documents()
        total_documents = len(documents)
        processing = len([document for document in documents if document["processing_status"] in {"uploading", "extracting", "indexing"}])
        failed = len([document for document in documents if document["processing_status"] == "failed"])
        pending = len([document for document in documents if document["lifecycle_status"] == "pending_review"])
        indexed = len([document for document in documents if document["processing_status"] == "completed"])
        lightrag_health = self._get_lightrag_health_snapshot()["status"]
        return {
            "total_documents": total_documents,
            "indexed": indexed,
            "processing": processing,
            "failed": failed,
            "pending": pending,
            "lightrag_health": lightrag_health,
        }

    def get_pipeline_status(self) -> dict:
        jobs = self.store.list_all_jobs()
        active_jobs = [job for job in jobs if job["status"] not in {"completed", "failed"}]
        completed_jobs = [job for job in jobs if job["status"] == "completed"]
        last_processed = max((job["updated_at"] for job in completed_jobs), default=None)
        return {
            "is_processing": bool(active_jobs),
            "queue_size": len(active_jobs),
            "last_processed": last_processed,
            "error_message": None,
        }

    def get_graph_stats(self) -> dict:
        documents = self.store.list_all_documents()
        labels = sorted({tag for document in documents for tag in document["supplemental_metadata"]["tags"]})
        return {"total_labels": len(labels), "top_labels": labels[:20]}

    def get_health(self) -> dict:
        lightrag_health = self._get_lightrag_health_snapshot()
        return {"admin_api": "healthy", "lightrag": lightrag_health["status"], "lightrag_url": lightrag_health["url"]}
