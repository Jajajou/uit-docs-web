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
from time import sleep
import unicodedata
from urllib.parse import urlparse
from typing import Any, cast
from uuid import uuid4

from api.clients.langgraph_client import get_internal_langgraph_client, get_public_langgraph_client
from api.clients.lightrag_client import get_lightrag_client, get_public_lightrag_client
from api.config import settings
from api.errors import ApiServiceError
from api.schemas import Role
from api.services.chat_result_adapter import normalize_chat_result, normalize_reference_path
from api.services.fixtures import INTERNAL_EMAIL_DOMAIN, get_document_index_excerpt, normalize_workspace_state
from api.services.workspace_store import WorkspaceStateStore

INTERNAL_ROLES = {"teacher", "admin"}
DOCUMENT_ADMIN_ROLES = {"admin"}
PUBLIC_DOCUMENT_ROLES = {"guest", "student", "teacher"}
REDACTED_LABEL = "Đã ẩn trong giao diện công khai"
REDACTED_EMAIL = REDACTED_LABEL
INTERNAL_WORKSPACE_SOURCE_PREFIX = "admin-dashboard-live://"
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


def normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    return "".join(character for character in normalized if unicodedata.category(character) != "Mn")


class InMemoryWorkspaceService:
    """Provides contract-aligned data via per-entity store CRUD."""

    def __init__(self, store: WorkspaceStateStore | None = None) -> None:
        if store is None:
            raise ValueError("A workspace store must be provided.")
        self.store = store
        self._normalize_persisted_workspace_state()
        self._internal_workspace_seeded = False
        self._public_workspace_seeded = False

    def reset(self) -> None:
        self.store.reset()
        self._internal_workspace_seeded = False
        self._public_workspace_seeded = False

    def _normalize_persisted_workspace_state(self) -> None:
        snapshot = self.store.get_state()
        normalized_snapshot = normalize_workspace_state(snapshot)
        if normalized_snapshot != snapshot:
            self.store.save_state(cast(dict, normalized_snapshot))

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

    def _conversation_owner_key(
        self,
        role: Role,
        session: dict | None,
        session_token: str | None = None,
    ) -> str | None:
        if isinstance(session, dict):
            email = str(session.get("user", {}).get("email") or "").strip().lower()
            if email:
                return f"user:{email}"
            session_id = str(session.get("session_id") or "").strip().lower()
            if session_id:
                return f"session:{session_id}"
        if session_token:
            return f"token:{session_token.strip().lower()}"
        if role == "guest":
            return None
        return f"role:{role}"

    def _conversation_owner_aliases(
        self,
        role: Role,
        session: dict | None,
        session_token: str | None = None,
    ) -> set[str]:
        aliases: set[str] = set()
        preferred_owner = self._conversation_owner_key(role, session, session_token)
        if preferred_owner:
            aliases.add(preferred_owner)
        if role != "guest":
            aliases.add(f"role:{role}")
        if isinstance(session, dict):
            email = str(session.get("user", {}).get("email") or "").strip().lower()
            if email:
                aliases.add(f"user:{email}")
            session_id = str(session.get("session_id") or "").strip().lower()
            if session_id:
                aliases.add(f"session:{session_id}")
        if session_token:
            aliases.add(f"token:{session_token.strip().lower()}")
        return aliases

    def _conversation_visible_to_owner(
        self,
        conversation: dict,
        owner_key: str | None,
        owner_aliases: set[str] | None = None,
    ) -> bool:
        aliases = owner_aliases or ({owner_key} if owner_key else set())
        if not aliases:
            return False
        stored_owner = str(conversation.get("owner_key") or "").strip().lower()
        if not stored_owner:
            return True
        return stored_owner in aliases

    def _ensure_conversation_owner(
        self,
        conversation: dict,
        owner_key: str | None,
        owner_aliases: set[str] | None = None,
    ) -> dict:
        if owner_key is None:
            return conversation
        stored_owner = str(conversation.get("owner_key") or "").strip().lower()
        if stored_owner and stored_owner == owner_key:
            return conversation
        if stored_owner and owner_aliases and stored_owner not in owner_aliases:
            return conversation
        updated_conversation = deepcopy(conversation)
        updated_conversation["owner_key"] = owner_key
        self.store.upsert_conversation(updated_conversation)
        return updated_conversation

    def _list_owned_conversations(self, owner_key: str | None, owner_aliases: set[str] | None = None) -> list[dict]:
        aliases = owner_aliases or ({owner_key} if owner_key else set())
        if not aliases:
            return []
        owned: list[dict] = []
        for conversation in self.store.list_all_conversations():
            if not self._conversation_visible_to_owner(conversation, owner_key, aliases):
                continue
            owned.append(self._ensure_conversation_owner(conversation, owner_key, aliases))
        return owned

    def _find_owned_conversation(
        self,
        conversation_id: str,
        owner_key: str | None,
        owner_aliases: set[str] | None = None,
    ) -> dict | None:
        aliases = owner_aliases or ({owner_key} if owner_key else set())
        conversation = self.store.get_conversation_by_id(conversation_id)
        if conversation is None:
            return None
        if not self._conversation_visible_to_owner(conversation, owner_key, aliases):
            return None
        return self._ensure_conversation_owner(conversation, owner_key, aliases)

    def _conversation_response_payload(self, conversation: dict) -> dict:
        payload = deepcopy(conversation)
        payload.pop("owner_key", None)
        return payload

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
            redacted["title"] = "Tài liệu đang chờ kiểm duyệt nội bộ"
            redacted["excerpt"] = "Chi tiết nguồn đã được ẩn trong giao diện công khai."

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
            needle = normalize_search_text(search)
            documents = [
                document
                for document in documents
                if needle in normalize_search_text(document["title"])
                or needle in normalize_search_text(document["supplemental_metadata"]["issuing_unit"])
                or any(needle in normalize_search_text(tag) for tag in document["supplemental_metadata"]["tags"])
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
            needle = normalize_search_text(search)
            users = [
                user
                for user in users
                if needle in normalize_search_text(user["name"]) or needle in normalize_search_text(user["email"])
            ]
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
            needle = normalize_search_text(search)
            logs = [
                log
                for log in logs
                if needle in normalize_search_text(log["actor_name"])
                or needle in normalize_search_text(log["target_label"])
                or needle in normalize_search_text(log["action"])
            ]
        return logs

    # ── Conversations / Chat ──

    def list_conversations(
        self,
        scenario: str,
        role: Role = "guest",
        session: dict | None = None,
        session_token: str | None = None,
    ) -> list[dict]:
        if scenario == "empty":
            return []
        owner_key = self._conversation_owner_key(role, session, session_token)
        owner_aliases = self._conversation_owner_aliases(role, session, session_token)
        conversations = [
            self._conversation_response_payload(conversation)
            for conversation in self._list_owned_conversations(owner_key, owner_aliases)
        ]
        if self._is_document_admin(role):
            return conversations
        return [self._redact_conversation_for_public_surface(conversation) for conversation in conversations]

    def delete_conversation(
        self,
        conversation_id: str,
        role: Role = "guest",
        session: dict | None = None,
        session_token: str | None = None,
    ) -> None:
        owner_key = self._conversation_owner_key(role, session, session_token)
        owner_aliases = self._conversation_owner_aliases(role, session, session_token)
        conversation = self._find_owned_conversation(conversation_id, owner_key, owner_aliases)
        if conversation is None:
            self._raise(404, "conversation_not_found", "Không tìm thấy cuộc trò chuyện.")
        self.store.delete_conversation(conversation_id)

    def clear_conversations(
        self,
        role: Role = "guest",
        session: dict | None = None,
        session_token: str | None = None,
    ) -> None:
        owner_key = self._conversation_owner_key(role, session, session_token)
        owner_aliases = self._conversation_owner_aliases(role, session, session_token)
        for conversation in self._list_owned_conversations(owner_key, owner_aliases):
            self.store.delete_conversation(conversation["id"])

    def _build_mock_chat_reply(self, question: str, scenario: str) -> dict:
        return {
            "id": f"msg-{uuid4().hex[:8]}",
            "role": "assistant",
            "content": (
                f'Tôi tìm thấy thông tin liên quan đến: "{question}", nhưng độ tin cậy đang thấp và bạn nên đối chiếu thêm với phòng ban phụ trách.'
                if scenario == "low-confidence"
                else f'Đây là phản hồi từ /web backend cho câu hỏi: "{question}". Assistant sẽ ưu tiên tài liệu mới, có nguồn và cảnh báo nếu cần.'
            ),
            "created_at": utc_now_iso(),
            "confidence": 0.35 if scenario == "low-confidence" else 0.86,
            "references": [
                {
                    "id": "ref-response-001",
                    "title": "Thông báo học phí học kỳ 2" if scenario == "low-confidence" else "Quy định học vụ 2024-2025",
                    "href": "/documents/doc-002" if scenario == "low-confidence" else "/documents/doc-001",
                    "excerpt": "Trích đoạn mô phỏng để kiểm tra hợp đồng dữ liệu giữa frontend và backend.",
                    "status_label": "Pending review" if scenario == "low-confidence" else "Approved",
                }
            ],
            "warnings": (
                [{"code": "low_confidence", "message": "Độ tin cậy đang thấp vì metadata chưa đầy đủ."}]
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

    def _list_internal_chat_documents(self) -> list[dict]:
        return [
            document
            for document in self.store.list_all_documents()
            if document["lifecycle_status"] in {"approved", "archived"}
        ]

    def _question_requests_current_validity(self, question: str) -> bool:
        normalized_question = normalize_search_text(question)
        return any(
            marker in normalized_question
            for marker in (
                "con hieu luc",
                "het hieu luc",
                "hieu luc khong",
                "dang ap dung",
                "hien tai con",
            )
        )

    def _question_needs_strict_grounding(self, question: str) -> bool:
        return self._question_requests_current_validity(question) or self._question_requests_change_verification(question)

    def _minimum_grounding_score(self, question: str) -> float:
        normalized_question = normalize_search_text(question)
        threshold = 4.0
        if self._question_needs_strict_grounding(question):
            threshold += 1.5
        if any(phrase in normalized_question for phrase in ("hoc phi", "hoc bong", "dang ky mon hoc", "lich dang ky")):
            threshold += 0.5
        if "thong bao" in normalized_question:
            threshold += 0.5
        return threshold

    def _score_document_for_chat(self, document: dict, question: str) -> float:
        question_text = self._normalize_chat_text(question)
        question_tokens = self._normalize_chat_tokens(question)
        if not question_tokens:
            return 0.0

        title = self._normalize_chat_text(document["title"])
        tags = [self._normalize_chat_text(tag) for tag in document["supplemental_metadata"].get("tags", [])]
        tags_joined = " ".join(tags)
        issuing_unit = self._normalize_chat_text(document["supplemental_metadata"].get("issuing_unit"))
        notes = self._normalize_chat_text(document["supplemental_metadata"].get("notes"))
        excerpt = self._normalize_chat_text(self._build_document_index_excerpt(document))
        temporal_metadata = document.get("temporal_metadata", {})
        document_number = self._normalize_chat_text(temporal_metadata.get("document_number"))
        academic_year = self._normalize_chat_text(temporal_metadata.get("academic_year"))
        document_type = self._normalize_chat_text(temporal_metadata.get("document_type"))
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
            if token in document_type:
                score += 1.6
            if token in excerpt:
                score += 1.2
            if token in issuing_unit:
                score += 0.8
            if token in notes:
                score += 0.6
            if token in cohort_years:
                score += 1.6

        phrase_weights = {
            "thong bao hoc phi": 5.0,
            "hoc phi": 4.0,
            "hoc vu": 4.0,
            "hoc bong": 4.0,
            "tam hoan hoc phi": 4.5,
            "hoc phi hoc ky": 4.2,
            "dang ky mon hoc": 5.0,
            "lich dang ky": 4.5,
            "quy dinh": 3.5,
            "thong bao": 2.0,
        }
        combined_text = " ".join(
            filter(None, [title, tags_joined, notes, issuing_unit, document_number, academic_year, document_type, excerpt])
        )
        for phrase, weight in phrase_weights.items():
            if phrase in question_text and phrase in combined_text:
                score += weight

        topic_penalties = {
            "thong bao hoc phi": 4.8,
            "hoc phi": 2.8,
            "tam hoan hoc phi": 3.2,
            "hoc phi hoc ky": 3.6,
            "hoc bong": 2.6,
            "dang ky mon hoc": 3.0,
            "lich dang ky": 2.8,
        }
        for phrase, penalty in topic_penalties.items():
            if phrase in question_text and phrase not in combined_text:
                score -= penalty

        if self._question_requests_current_validity(question):
            if temporal_metadata.get("valid_from"):
                score += 1.8
            if temporal_metadata.get("valid_until"):
                score += 1.2
            if temporal_metadata.get("academic_year"):
                score += 0.8

        if temporal_metadata.get("academic_year") and academic_year and academic_year in question_text:
            score += 2.5

        if document["lifecycle_status"] == "archived":
            score -= 1.0

        return max(score, 0.0)

    def _score_public_document_for_chat(self, document: dict, question: str) -> float:
        return self._score_document_for_chat(document, question)

    def _rank_documents_for_chat(self, documents: list[dict], question: str) -> list[dict]:
        return sorted(
            (
                {
                    "document": document,
                    "score": self._score_document_for_chat(document, question),
                }
                for document in documents
            ),
            key=lambda item: item["score"],
            reverse=True,
        )

    def _build_public_reference_excerpt(self, document: dict) -> str:
        temporal_metadata = document.get("temporal_metadata", {})
        document_number = temporal_metadata.get("document_number")
        valid_from = temporal_metadata.get("valid_from")
        valid_until = temporal_metadata.get("valid_until")
        excerpt = self._build_document_index_excerpt(document)

        parts: list[str] = []
        if document_number:
            parts.append(str(document_number))
        if valid_from and valid_until:
            parts.append(f"Hiệu lực từ {valid_from} đến {valid_until}.")
        elif valid_from:
            parts.append(f"Có thông tin hiệu lực từ {valid_from}.")
        if excerpt:
            parts.append(excerpt.splitlines()[0].strip())
        return " ".join(parts).strip() or "Tài liệu công khai được phê duyệt để tra cứu trên UIT AI."

    def _build_public_reference(self, document: dict) -> dict:
        return {
            "id": f"ref-public-{document['id']}",
            "title": document["title"],
            "href": f"/documents/{document['id']}",
            "excerpt": self._build_public_reference_excerpt(document),
            "status_label": self._status_label_for_reference_document(document),
        }

    def _build_public_answer_intro(self, question: str) -> str:
        normalized_question = normalize_search_text(question)
        if "lich dang ky" in normalized_question or ("dang ky" in normalized_question and "mon hoc" in normalized_question):
            return "Theo các tài liệu công khai UIT đang được trích dẫn về lịch đăng ký môn học:"
        if "hoc phi" in normalized_question:
            return "Theo các tài liệu công khai UIT đang được trích dẫn về học phí:"
        if "hoc bong" in normalized_question:
            return "Theo các tài liệu công khai UIT đang được trích dẫn về học bổng:"
        if "hoc vu" in normalized_question or "quy dinh" in normalized_question:
            return "Theo các tài liệu công khai UIT đang được trích dẫn về học vụ:"
        return "Theo các tài liệu công khai UIT đang được trích dẫn:"

    def _rank_reference_documents_for_chat(self, references: list[dict], question: str) -> list[dict]:
        ranked: list[dict] = []
        for reference in references:
            document = self._find_document_for_reference(self._reference_file_path(reference))
            score = self._score_document_for_chat(document, question) if document is not None else 0.0
            ranked.append(
                {
                    "reference": reference,
                    "document": document,
                    "score": score,
                }
            )
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked

    def _filter_references_for_chat(self, references: list[dict], question: str) -> tuple[list[dict], list[dict]]:
        ranked = self._rank_reference_documents_for_chat(references, question)
        filtered: list[dict] = []
        seen_hrefs: set[str] = set()
        for item in ranked:
            reference = item["reference"]
            href = str(reference.get("href") or "")
            if href and href in seen_hrefs:
                continue
            if item["score"] <= 0 and filtered and not href.startswith(("http://", "https://")):
                continue
            filtered.append(reference)
            if href:
                seen_hrefs.add(href)
            if len(filtered) >= 4:
                break
        return (filtered or references[:3], ranked)

    def _references_have_strong_grounding(self, ranked_reference_documents: list[dict], question: str) -> bool:
        if not ranked_reference_documents:
            return False
        return ranked_reference_documents[0]["score"] >= self._minimum_grounding_score(question)

    def _build_low_grounding_chat_reply(
        self,
        question: str,
        references: list[dict],
        *,
        public_surface: bool,
        ranked_reference_documents: list[dict] | None = None,
    ) -> dict:
        ranked = ranked_reference_documents or self._rank_reference_documents_for_chat(references, question)
        filtered_references = [item["reference"] for item in ranked if item["score"] > 0][:2] or references[:1]
        top_document = ranked[0]["document"] if ranked else None

        if top_document is not None:
            document_number = str(top_document.get("temporal_metadata", {}).get("document_number") or "").strip()
            label = f'"{top_document["title"]}"'
            if document_number:
                label += f" ({document_number})"
            detail = (
                f"Nguồn khớp nhất hiện tại là {label}, nhưng mức liên quan chưa đủ mạnh "
                "để xác nhận trực tiếp kết luận này."
            )
        else:
            detail = "Các nguồn đang đối chiếu chưa khớp đủ mạnh với đúng chủ đề bạn hỏi."

        if self._question_needs_strict_grounding(question):
            content = (
                "Hiện tôi chưa có đủ căn cứ để kết luận chắc chắn. "
                f"{detail} Bạn nên đối chiếu đúng thông báo hoặc văn bản cần xác minh trước khi chốt kết luận."
            )
        else:
            content = (
                "Hiện tôi mới tìm thấy một số nguồn liên quan gián tiếp. "
                f"{detail} Tôi cần thêm nguồn khớp trực tiếp hơn để trả lời chắc chắn."
            )

        return {
            "id": f"msg-{uuid4().hex[:8]}",
            "role": "assistant",
            "content": content,
            "created_at": utc_now_iso(),
            "confidence": 0.32 if public_surface else 0.38,
            "references": filtered_references,
            "warnings": [
                {
                    "code": "insufficient_grounding",
                    "message": (
                        "Nguồn truy xuất hiện mới dừng ở mức liên quan, chưa đủ mạnh để xác nhận trực tiếp câu trả lời."
                    ),
                }
            ],
        }

    def _parse_temporal_date(self, value: str | None) -> datetime | None:
        raw_value = str(value or "").strip()
        if not raw_value:
            return None
        try:
            return datetime.strptime(raw_value, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return None

    def _build_temporal_validity_answer(self, question: str, document: dict | None) -> str | None:
        if document is None or not self._question_requests_current_validity(question):
            return None

        temporal_metadata = document.get("temporal_metadata", {})
        valid_from = str(temporal_metadata.get("valid_from") or "").strip()
        valid_until = str(temporal_metadata.get("valid_until") or "").strip()
        academic_year = str(temporal_metadata.get("academic_year") or "").strip()
        if not valid_from and not valid_until:
            return None

        label = f'"{document["title"]}"'
        document_number = str(temporal_metadata.get("document_number") or "").strip()
        if document_number:
            label += f" ({document_number})"

        now_date = datetime.now(UTC).date()
        from_date = self._parse_temporal_date(valid_from)
        until_date = self._parse_temporal_date(valid_until)

        if from_date is not None and until_date is not None:
            if from_date.date() <= now_date <= until_date.date():
                status_line = f"Theo metadata hiện có, {label} đang trong thời gian hiệu lực từ {valid_from} đến {valid_until}."
            elif now_date < from_date.date():
                status_line = f"Theo metadata hiện có, {label} chưa đến thời điểm áp dụng; mốc hiệu lực bắt đầu từ {valid_from}."
            else:
                status_line = f"Theo metadata hiện có, {label} đã hết hiệu lực sau ngày {valid_until}."
        elif from_date is not None:
            status_line = f"Theo metadata hiện có, {label} được ghi nhận áp dụng từ {valid_from}."
        else:
            status_line = f"Theo metadata hiện có, {label} có mốc hiệu lực đến {valid_until}."

        notes: list[str] = []
        if academic_year:
            notes.append(f"Tài liệu này gắn với ngữ cảnh năm học {academic_year}.")
        if not valid_until:
            notes.append("Nguồn hiện chưa nêu rõ mốc kết thúc nên vẫn cần đối chiếu thêm thông báo mới hơn trước khi kết luận chắc chắn.")

        return " ".join([status_line, *notes]).strip()

    def _question_requests_change_verification(self, question: str) -> bool:
        normalized_question = normalize_search_text(question)
        return any(term in normalized_question for term in ("thay doi", "cap nhat", "dieu chinh", "khac truoc"))

    def _references_explicitly_confirm_change(self, references: list[dict]) -> bool:
        change_terms = ("thay doi", "cap nhat", "dieu chinh", "sua doi", "khong thay doi")
        for reference in references:
            normalized_excerpt = normalize_search_text(str(reference.get("excerpt") or ""))
            if any(term in normalized_excerpt for term in change_terms):
                return True
        return False

    def _format_reference_excerpt_for_answer(self, excerpt: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(excerpt or "")).strip()
        return cleaned.rstrip(".")

    def _build_grounded_public_answer(self, question: str, references: list[dict]) -> str:
        answer_lines = [self._build_public_answer_intro(question), ""]

        for reference in references[:2]:
            excerpt = self._format_reference_excerpt_for_answer(str(reference.get("excerpt") or ""))
            if not excerpt:
                continue
            answer_lines.append(f"- {reference['title']}: {excerpt}.")

        if self._question_requests_change_verification(question) and not self._references_explicitly_confirm_change(references):
            answer_lines.extend(
                [
                    "",
                    "Chưa thấy tài liệu công khai trong các nguồn trên xác nhận có thay đổi. Bộ nguồn hiện tại chủ yếu cho biết phạm vi áp dụng và mốc thời gian hiệu lực.",
                ]
            )

        answer_lines.extend(
            [
                "",
                'Mở mục "Nguồn tài liệu" để kiểm tra số hiệu, thời gian hiệu lực và phạm vi áp dụng trước khi kết luận.',
            ]
        )

        return "\n".join(line for line in answer_lines if line is not None).strip()

    def _select_public_live_answer_content(
        self,
        question: str,
        raw_response: str,
        references: list[dict],
        ranked_reference_documents: list[dict],
    ) -> str:
        top_document = ranked_reference_documents[0]["document"] if ranked_reference_documents else None
        return (
            self._build_temporal_validity_answer(question, top_document)
            or raw_response
            or self._build_grounded_public_answer(question, references)
        )

    def _sanitize_lightrag_response_text(self, raw_response: str) -> str:
        cleaned_lines: list[str] = []
        for line in str(raw_response or "").splitlines():
            stripped = line.strip()
            normalized = normalize_search_text(stripped) if stripped else ""
            if "tai lieu tham khao" in normalized or normalized in {"reference", "references"}:
                break
            if "tai lieu da duoc sua doi" in normalized or "tinh minh bach" in normalized:
                break
            if "admin-dashboard-public://" in line or "/uploads/" in line:
                continue
            cleaned_lines.append(line)
        cleaned = "\n".join(cleaned_lines).strip()
        cleaned = re.sub(
            r"(?:\n|\r\n)?#{1,6}\s*(?:Tài liệu tham khảo|Tai lieu tham khao|References?)\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        cleaned = re.sub(r"(?:\n|\r\n)?---\s*$", "", cleaned).strip()
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return self._sanitize_chat_message_content(cleaned)

    def _sanitize_chat_message_content(self, raw_content: str) -> str:
        cleaned = str(raw_content or "").replace("\r\n", "\n").strip()
        if not cleaned:
            return ""

        cleaned = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", cleaned)
        cleaned = re.sub(r"(?<!\*)\*\*(.+?)\*\*(?!\*)", r"\1", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"(?<!_)__(.+?)__(?!_)", r"\1", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
        cleaned = re.sub(r"^[ \t]*#{1,6}[ \t]*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^[ \t]*>[ \t]?", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.replace("**", "").replace("__", "")
        cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _public_workspace_source(self, document_id: str) -> str:
        return f"{PUBLIC_WORKSPACE_SOURCE_PREFIX}{document_id}"

    def _internal_workspace_source(self, document_id: str) -> str:
        return f"{INTERNAL_WORKSPACE_SOURCE_PREFIX}{document_id}"

    def _extract_document_id_from_public_source(self, file_path: str) -> str | None:
        normalized = str(file_path or "").strip()
        if normalized.startswith(PUBLIC_WORKSPACE_SOURCE_PREFIX):
            return normalized.removeprefix(PUBLIC_WORKSPACE_SOURCE_PREFIX).strip() or None
        if normalized.startswith(INTERNAL_WORKSPACE_SOURCE_PREFIX):
            return normalized.removeprefix(INTERNAL_WORKSPACE_SOURCE_PREFIX).strip() or None
        return None

    def _should_sync_document_to_public_workspace(self, document: dict) -> bool:
        return (
            document.get("lifecycle_status") == "approved"
            and document.get("supplemental_metadata", {}).get("visibility_scope") == "public"
            and not document.get("system_metadata", {}).get("is_archived", False)
        )

    def _should_sync_document_to_internal_workspace(self, document: dict) -> bool:
        return (
            document.get("lifecycle_status") == "approved"
            and not document.get("system_metadata", {}).get("is_archived", False)
        )

    def _build_document_index_excerpt(self, document: dict) -> str:
        temporal_metadata = document.get("temporal_metadata", {})
        supplemental_metadata = document.get("supplemental_metadata", {})
        traceability = document.get("traceability", {})

        candidates: list[str] = []
        seeded_excerpt = get_document_index_excerpt(str(document.get("id") or ""))
        if seeded_excerpt:
            candidates.append(seeded_excerpt)

        notes = str(supplemental_metadata.get("notes") or "").strip()
        if notes:
            candidates.append(notes)

        publication_reason = str(traceability.get("publication_reason") or "").strip()
        if publication_reason:
            candidates.append(publication_reason)

        temporal_reasoning = str(temporal_metadata.get("temporal_reasoning") or "").strip()
        if temporal_reasoning:
            candidates.append(temporal_reasoning)

        for version_entry in document.get("version_history", []):
            change_summary = str(version_entry.get("change_summary") or "").strip()
            if change_summary:
                candidates.append(change_summary)
            for highlight in version_entry.get("change_highlights", []):
                highlight_text = str(highlight or "").strip()
                if highlight_text:
                    candidates.append(highlight_text)

        seen: set[str] = set()
        excerpt_blocks: list[str] = []
        for candidate in candidates:
            normalized_candidate = self._normalize_chat_text(candidate)
            if not normalized_candidate or normalized_candidate in seen:
                continue
            seen.add(normalized_candidate)
            excerpt_blocks.append(candidate)
            if len(excerpt_blocks) >= 4:
                break

        return "\n\n".join(excerpt_blocks)

    def _build_public_workspace_document_text(self, document: dict) -> str:
        temporal_metadata = document.get("temporal_metadata", {})
        supplemental_metadata = document.get("supplemental_metadata", {})
        excerpt = self._build_document_index_excerpt(document)
        lines = [
            f"Tiêu đề: {document['title']}",
        ]
        if excerpt:
            lines.append("Trích yếu nội dung:")
            lines.append(excerpt)
        lines.extend(
            [
                f"Trạng thái công bố: {document.get('lifecycle_status')}",
                f"Phạm vi hiển thị: {supplemental_metadata.get('visibility_scope')}",
            ]
        )
        document_number = temporal_metadata.get("document_number")
        if document_number:
            lines.append(f"Số hiệu: {document_number}")
        issuing_unit = supplemental_metadata.get("issuing_unit")
        if issuing_unit:
            lines.append(f"Đơn vị ban hành: {issuing_unit}")
        document_type = temporal_metadata.get("document_type")
        if document_type:
            lines.append(f"Loại tài liệu: {document_type}")
        academic_year = temporal_metadata.get("academic_year")
        if academic_year:
            lines.append(f"Năm học: {academic_year}")
        valid_from = temporal_metadata.get("valid_from")
        valid_until = temporal_metadata.get("valid_until")
        if valid_from and valid_until:
            lines.append(f"Hiệu lực: từ {valid_from} đến {valid_until}")
        elif valid_from:
            lines.append(f"Hiệu lực: từ {valid_from}")
        cohort_years = temporal_metadata.get("cohort_years") or []
        if cohort_years:
            lines.append(f"Khóa tuyển sinh liên quan: {', '.join(cohort_years)}")
        tags = supplemental_metadata.get("tags") or []
        if tags:
            lines.append(f"Nhãn: {', '.join(tags)}")
        return "\n".join(lines)

    def _sync_public_workspace_document(self, document: dict) -> dict:
        if not settings.LIVE_INGESTION_MODE or not settings.LIGHTRAG_PUBLIC_URL:
            return {"status": "skipped", "source": "public-live-disabled"}

        client = get_public_lightrag_client()
        file_source = self._public_workspace_source(document["id"])
        existing_ids = self._public_workspace_remote_document_ids(client, file_source)
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

    def _sync_internal_workspace_document(self, document: dict) -> dict:
        if not settings.LIVE_INGESTION_MODE:
            return {"status": "skipped", "source": "live-disabled"}

        client = get_lightrag_client()
        file_source = self._internal_workspace_source(document["id"])
        existing_ids = self._internal_workspace_remote_document_ids(client, file_source)
        if existing_ids:
            client.delete_document(existing_ids)

        result = client.insert_text(
            self._build_public_workspace_document_text(document),
            source=file_source,
        )
        if result.get("error"):
            self._internal_workspace_seeded = False
            return {"status": "error", "source": "lightrag-internal", "raw": result}
        return {"status": "accepted", "source": "lightrag-internal", "raw": result}

    def _remove_public_workspace_document(self, document_id: str) -> dict:
        if not settings.LIVE_INGESTION_MODE or not settings.LIGHTRAG_PUBLIC_URL:
            return {"status": "skipped", "source": "public-live-disabled"}

        client = get_public_lightrag_client()
        existing_ids = self._public_workspace_remote_document_ids(
            client,
            self._public_workspace_source(document_id),
        )
        if not existing_ids:
            return {"status": "not_found", "source": "lightrag-public"}
        result = client.delete_document(existing_ids)
        if result.get("error"):
            self._public_workspace_seeded = False
            return {"status": "error", "source": "lightrag-public", "raw": result}
        return {"status": "deleted", "source": "lightrag-public", "raw": result}

    def _public_workspace_remote_documents(self, client: Any, file_source: str) -> list[dict]:
        if hasattr(client, "find_documents_by_file_path"):
            documents = client.find_documents_by_file_path(file_source)
            if isinstance(documents, list):
                return [document for document in documents if isinstance(document, dict)]
        document_ids = client.find_document_ids_by_file_path(file_source)
        return [{"id": document_id, "status": "processed"} for document_id in document_ids]

    def _internal_workspace_remote_documents(self, client: Any, file_source: str) -> list[dict]:
        if hasattr(client, "find_documents_by_file_path"):
            documents = client.find_documents_by_file_path(file_source)
            if isinstance(documents, list):
                return [document for document in documents if isinstance(document, dict)]
        document_ids = client.find_document_ids_by_file_path(file_source)
        return [{"id": document_id, "status": "processed"} for document_id in document_ids]

    def _public_workspace_remote_document_ids(self, client: Any, file_source: str) -> list[str]:
        return [
            document_id
            for document in self._public_workspace_remote_documents(client, file_source)
            if (document_id := str(document.get("id") or "").strip())
        ]

    def _internal_workspace_remote_document_ids(self, client: Any, file_source: str) -> list[str]:
        return [
            document_id
            for document in self._internal_workspace_remote_documents(client, file_source)
            if (document_id := str(document.get("id") or "").strip())
        ]

    def _public_workspace_status_for_document(self, client: Any, document_id: str) -> str:
        remote_documents = self._public_workspace_remote_documents(
            client,
            self._public_workspace_source(document_id),
        )
        if not remote_documents:
            return "missing"
        statuses = {str(document.get("status") or "").strip().lower() for document in remote_documents}
        if "failed" in statuses:
            return "failed"
        if statuses & {"processing", "pending", "queued"}:
            return "processing"
        if statuses & {"processed", "completed", "success"}:
            return "processed"
        return "unknown"

    def _internal_workspace_status_for_document(self, client: Any, document_id: str) -> str:
        remote_documents = self._internal_workspace_remote_documents(
            client,
            self._internal_workspace_source(document_id),
        )
        if not remote_documents:
            return "missing"
        statuses = {str(document.get("status") or "").strip().lower() for document in remote_documents}
        if "failed" in statuses:
            return "failed"
        if statuses & {"processing", "pending", "queued"}:
            return "processing"
        if statuses & {"processed", "completed", "success"}:
            return "processed"
        return "unknown"

    def _ensure_public_workspace_seeded(self) -> None:
        if self._public_workspace_seeded:
            return
        if not settings.LIVE_INGESTION_MODE or not settings.LIGHTRAG_PUBLIC_URL:
            return

        client = get_public_lightrag_client()
        synced_ok = True
        ready = True
        for document in self.store.list_all_documents():
            try:
                if self._should_sync_document_to_public_workspace(document):
                    status = self._public_workspace_status_for_document(client, document["id"])
                    if status == "processed":
                        continue
                    if status == "processing":
                        ready = False
                        continue
                    result = self._sync_public_workspace_document(document)
                    ready = False
                else:
                    result = self._remove_public_workspace_document(document["id"])
                if result.get("status") == "error":
                    synced_ok = False
            except Exception:
                synced_ok = False
        self._public_workspace_seeded = synced_ok and ready

    def _ensure_internal_workspace_seeded(self) -> None:
        if self._internal_workspace_seeded:
            return
        if not settings.LIVE_INGESTION_MODE:
            return

        client = get_lightrag_client()
        synced_ok = True
        ready = True
        for document in self.store.list_all_documents():
            try:
                if self._should_sync_document_to_internal_workspace(document):
                    status = self._internal_workspace_status_for_document(client, document["id"])
                    if status == "processed":
                        continue
                    if status == "processing":
                        ready = False
                        continue
                    result = self._sync_internal_workspace_document(document)
                    ready = False
                else:
                    result = {"status": "skipped", "source": "not-indexable"}
                if result.get("status") == "error":
                    synced_ok = False
            except Exception:
                synced_ok = False
        self._internal_workspace_seeded = synced_ok and ready

    def _wait_for_public_workspace_ready(self, timeout_seconds: int = 15) -> None:
        if self._public_workspace_seeded:
            return
        if not settings.LIVE_INGESTION_MODE or not settings.LIGHTRAG_PUBLIC_URL:
            return

        deadline = datetime.now(UTC).timestamp() + timeout_seconds
        while datetime.now(UTC).timestamp() < deadline:
            self._ensure_public_workspace_seeded()
            if self._public_workspace_seeded:
                return
            sleep(2)

    def _wait_for_internal_workspace_ready(self, timeout_seconds: int = 15) -> None:
        if self._internal_workspace_seeded:
            return
        if not settings.LIVE_INGESTION_MODE:
            return

        deadline = datetime.now(UTC).timestamp() + timeout_seconds
        while datetime.now(UTC).timestamp() < deadline:
            self._ensure_internal_workspace_seeded()
            if self._internal_workspace_seeded:
                return
            sleep(2)

    def _force_public_workspace_reseed(self) -> None:
        if not settings.LIVE_INGESTION_MODE or not settings.LIGHTRAG_PUBLIC_URL:
            return

        self._public_workspace_seeded = False
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
        if not synced_ok:
            return
        self._wait_for_public_workspace_ready()

    def _force_internal_workspace_reseed(self) -> None:
        if not settings.LIVE_INGESTION_MODE:
            return

        self._internal_workspace_seeded = False
        synced_ok = True
        for document in self.store.list_all_documents():
            try:
                if self._should_sync_document_to_internal_workspace(document):
                    result = self._sync_internal_workspace_document(document)
                else:
                    result = {"status": "skipped", "source": "not-indexable"}
                if result.get("status") == "error":
                    synced_ok = False
            except Exception:
                synced_ok = False
        if not synced_ok:
            return
        self._wait_for_internal_workspace_ready()

    def _reconcile_document_public_workspace(self, document: dict | None) -> dict:
        if document is None:
            return {"status": "skipped", "source": "missing-document"}
        if self._should_sync_document_to_public_workspace(document):
            return self._sync_public_workspace_document(document)
        return self._remove_public_workspace_document(document["id"])

    def _build_public_catalog_chat_reply(self, question: str) -> dict:
        matches = self._rank_documents_for_chat(self._list_public_chat_documents(), question)

        strong_matches = [item for item in matches if item["score"] >= 3.0]
        if not strong_matches:
            return {
                "id": f"msg-{uuid4().hex[:8]}",
                "role": "assistant",
                "content": (
                    "Tôi chưa tìm thấy tài liệu công khai phù hợp trong hệ thống để trả lời câu hỏi này. "
                    "Bạn nên nêu rõ hơn chủ đề hoặc đối chiếu thêm với đơn vị phụ trách của UIT."
                ),
                "created_at": utc_now_iso(),
                "confidence": 0.28,
                "references": [],
                "warnings": [
                    {
                        "code": "low_confidence",
                        "message": "Không tìm thấy tài liệu công khai có độ phù hợp đủ cao để đưa ra câu trả lời có nguồn.",
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

        summary_parts = [f'Tài liệu công khai phù hợp nhất hiện tại là "{top_match["title"]}"']
        if document_number:
            summary_parts[-1] += f" ({document_number})"
        summary_parts[-1] += "."
        if valid_from and valid_until:
            summary_parts.append(f"Tài liệu này có hiệu lực từ {valid_from} đến {valid_until}.")
        elif valid_from:
            summary_parts.append(f"Tài liệu này ghi nhận mốc áp dụng từ {valid_from}.")
        if academic_year:
            summary_parts.append(f"Dữ liệu đang gắn với năm học {academic_year}.")
        if cohort_years:
            summary_parts.append(f"Các khóa được đề cập gồm {', '.join(cohort_years)}.")
        notes = str(top_match["supplemental_metadata"].get("notes") or "").strip()
        if notes:
            summary_parts.append(notes)
        if top_match["lifecycle_status"] == "archived":
            summary_parts.append("Đây là tài liệu lưu trữ, bạn nên đối chiếu thêm với thông báo mới nhất nếu cần xác nhận.")

        warnings: list[dict] = []
        confidence = 0.76
        if top_match["lifecycle_status"] == "archived":
            confidence = 0.44
            warnings.append(
                {
                    "code": "archived_source",
                    "message": "Nguồn tham chiếu chính là tài liệu đã lưu trữ, có thể không còn là hướng dẫn mới nhất.",
                }
            )
        elif strong_matches[0]["score"] < 5.0:
            confidence = 0.58
            warnings.append(
                {
                    "code": "low_confidence",
                    "message": "Đã tìm thấy tài liệu công khai liên quan, nhưng bạn nên đối chiếu thêm với phòng ban phụ trách.",
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

    def _build_public_live_query(self, question: str) -> str:
        return str(question or "").strip()
        return "\n".join(
            [
                "Trả lời chỉ dựa trên ngữ cảnh đã truy xuất từ tài liệu công khai của UIT.",
                "Phân biệt rõ giữa khóa tuyển sinh và năm học.",
                "Nếu tài liệu nói áp dụng cho sinh viên khóa tuyển sinh 2024, 2025, 2026 thì phải nêu đúng như vậy.",
                "Nếu không có thông tin về thay đổi, hãy nói rõ là chưa thấy tài liệu công khai nào xác nhận thay đổi.",
                f"Câu hỏi: {question}",
            ]
        )

    def _query_internal_live_chat_result(self, question: str, conversation: dict | None) -> dict:
        conversation_history = self._build_chat_conversation_history(conversation)
        if not settings.TEST_MODE:
            result = get_internal_langgraph_client().query_text(
                question,
                conversation_history=conversation_history,
                include_references=True,
                include_chunk_content=True,
                response_type="Multiple Paragraphs",
            )
            if not result.get("error"):
                return result

        return get_lightrag_client().query_text(
            question,
            conversation_history=conversation_history,
            mode="mix",
            include_references=True,
            include_chunk_content=True,
            response_type="Multiple Paragraphs",
        )

    def _query_public_live_chat_result(self, question: str, conversation: dict | None) -> dict:
        conversation_history = self._build_chat_conversation_history(conversation)
        if settings.LANGGRAPH_PUBLIC_ASSISTANT_ID and not settings.TEST_MODE:
            result = get_public_langgraph_client().query_text(
                question,
                conversation_history=conversation_history,
                include_references=True,
                include_chunk_content=True,
                response_type="Multiple Paragraphs",
            )
            if not result.get("error"):
                return result

        return get_public_lightrag_client().query_text(
            question,
            conversation_history=conversation_history,
            mode="mix",
            include_references=True,
            include_chunk_content=True,
            response_type="Multiple Paragraphs",
        )

    def _should_use_live_chat(self, role: Role, scenario: str) -> bool:
        return settings.LIVE_INGESTION_MODE and role in {"teacher", "admin"} and scenario == "happy"

    def _should_use_public_live_chat(self, role: Role, scenario: str) -> bool:
        return (
            settings.LIVE_INGESTION_MODE
            and bool(settings.LIGHTRAG_PUBLIC_URL or settings.LANGGRAPH_PUBLIC_ASSISTANT_ID)
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
        href_document_id = self._extract_document_id_from_href(file_path)
        if href_document_id:
            return self.store.get_document_by_id(href_document_id)
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

    def _reference_file_path(self, reference: dict) -> str:
        return normalize_reference_path(reference)

    def _status_label_for_reference_document(self, document: dict | None) -> str:
        if document is None:
            return "Indexed"
        lifecycle_status = document.get("lifecycle_status")
        if lifecycle_status == "approved":
            return "Approved"
        if lifecycle_status == "archived":
            return "Archived"
        return "Pending review"

    def _response_type_warning(
        self,
        response_type: str,
        *,
        public_surface: bool,
    ) -> dict | None:
        if response_type == "partial_answer":
            return {
                "code": "partial_answer",
                "message": (
                    "\u0110\u00e3 t\u00ecm th\u1ea5y ng\u1eef c\u1ea3nh li\u00ean quan, "
                    "nh\u01b0ng c\u00e2u tr\u1ea3 l\u1eddi hi\u1ec7n m\u1edbi bao qu\u00e1t m\u1ed9t ph\u1ea7n th\u00f4ng tin."
                ),
            }
        if response_type == "fallback":
            return {
                "code": "follow_up_recommended",
                "message": (
                    "\u1ee8ng d\u1ee5ng ch\u1ec9 x\u00e1c nh\u1eadn \u0111\u01b0\u1ee3c m\u1ed9t ph\u1ea7n ng\u1eef c\u1ea3nh. "
                    + (
                        "B\u1ea1n n\u00ean m\u1edf m\u1ee5c \"Ngu\u1ed3n t\u00e0i li\u1ec7u\" \u0111\u1ec3 \u0111\u1ed1i chi\u1ebfu th\u00eam."
                        if public_surface
                        else "B\u1ea1n n\u00ean \u0111\u1ed1i chi\u1ebfu th\u00eam v\u1edbi \u0111\u01a1n v\u1ecb ph\u1ee5 tr\u00e1ch."
                    )
                ),
            }
        return None

    def _live_chat_confidence(
        self,
        response_type: str,
        *,
        reference_count: int,
        no_context: bool,
        public_surface: bool,
    ) -> float:
        if no_context or reference_count == 0:
            return 0.34 if not public_surface else 0.48
        if public_surface:
            if response_type == "partial_answer":
                return 0.62 if reference_count >= 2 else 0.56
            if response_type == "fallback":
                return 0.5
            return 0.76 if reference_count >= 2 else 0.68
        if response_type == "partial_answer":
            return 0.66
        if response_type == "fallback":
            return 0.48
        return 0.82

    def _build_live_reference(self, reference: dict) -> dict:
        document = self._find_document_for_reference(self._reference_file_path(reference))
        if document is not None:
            return {
                "id": str(reference.get("reference_id") or f"ref-{uuid4().hex[:8]}"),
                "title": document["title"],
                "href": f"/documents/{document['id']}",
                "excerpt": "Nguồn được truy xuất từ cơ sở tri thức LightRAG và đã được ánh xạ về tài liệu nội bộ.",
                "status_label": self._status_label_for_reference_document(document),
            }
        fallback_href = str(reference.get("href") or reference.get("url") or self._reference_file_path(reference) or "/documents")
        if fallback_href.startswith(("http://", "https://")):
            return {
                "id": str(reference.get("reference_id") or f"ref-{uuid4().hex[:8]}"),
                "title": str(reference.get("title") or "Nguồn tài liệu hệ thống"),
                "href": fallback_href,
                "excerpt": str(reference.get("excerpt") or "Nguồn được trích trực tiếp từ câu trả lời live."),
                "status_label": "Indexed",
            }
        return {
            "id": str(reference.get("reference_id") or f"ref-{uuid4().hex[:8]}"),
            "title": "Nguồn tài liệu hệ thống",
            "href": "/documents",
            "excerpt": "Nguồn được trả về từ truy vấn LightRAG.",
            "status_label": "Indexed",
        }

    def _build_public_live_reference(self, reference: dict) -> dict:
        document = self._find_document_for_reference(self._reference_file_path(reference))
        if document is not None:
            return {
                "id": str(reference.get("reference_id") or f"ref-{uuid4().hex[:8]}"),
                "title": document["title"],
                "href": f"/documents/{document['id']}",
                "excerpt": self._build_public_reference_excerpt(document),
                "status_label": self._status_label_for_reference_document(document),
            }
        fallback_href = str(reference.get("href") or reference.get("url") or self._reference_file_path(reference) or "/documents")
        if fallback_href.startswith(("http://", "https://")):
            return {
                "id": str(reference.get("reference_id") or f"ref-{uuid4().hex[:8]}"),
                "title": str(reference.get("title") or "Tài liệu công khai UIT"),
                "href": fallback_href,
                "excerpt": str(reference.get("excerpt") or "Nguồn được trích trực tiếp từ câu trả lời live của UIT AI."),
                "status_label": "Approved",
            }
        return {
            "id": str(reference.get("reference_id") or f"ref-{uuid4().hex[:8]}"),
            "title": "Tài liệu công khai UIT",
            "href": "/documents",
            "excerpt": "Nguồn được trả về từ không gian tri thức công khai của UIT AI.",
            "status_label": "Approved",
        }

    def _build_live_chat_reply_legacy(self, question: str, conversation: dict | None) -> dict:
        self._ensure_internal_workspace_seeded()
        self._wait_for_internal_workspace_ready()
        result = self._query_internal_live_chat_result(question, conversation)
        if result.get("error"):
            self._raise(502, "live_query_failed", "Live chat query failed while generating the answer.")

        normalized = normalize_chat_result(result)
        raw_response = self._sanitize_lightrag_response_text(normalized.response_text)
        references = [self._build_live_reference(reference) for reference in normalized.references]
        no_context = normalized.no_context or not references
        if no_context or not references:
            self._force_internal_workspace_reseed()
            result = self._query_internal_live_chat_result(question, conversation)
            if result.get("error"):
                self._raise(502, "live_query_failed", "Live chat query failed while generating the answer.")
            normalized = normalize_chat_result(result)
            raw_response = self._sanitize_lightrag_response_text(normalized.response_text)
            references = [self._build_live_reference(reference) for reference in normalized.references]
            no_context = normalized.no_context or not references
        references, ranked_reference_documents = self._filter_references_for_chat(references, question)
        if no_context or not self._references_have_strong_grounding(ranked_reference_documents, question):
            return self._build_low_grounding_chat_reply(
                question,
                references,
                public_surface=False,
                ranked_reference_documents=ranked_reference_documents,
            )
        warnings: list[dict] = []
        response_type_warning = self._response_type_warning(normalized.response_type, public_surface=False)
        if response_type_warning is not None:
            warnings.append(response_type_warning)
        top_document = ranked_reference_documents[0]["document"] if ranked_reference_documents else None
        final_content = self._build_temporal_validity_answer(question, top_document) or raw_response
        if False:
            warnings.append(
                {
                    "code": "low_confidence",
                    "message": (
                        "\u0110\u1ed9 tin c\u1eady \u0111ang th\u1ea5p v\u00ec truy v\u1ea5n live "
                        "ch\u01b0a tr\u1ea3 v\u1ec1 ngu\u1ed3n tham chi\u1ebfu \u0111\u1ee7 ch\u1eafc ch\u1eafn."
                    ),
                }
            )
        else:
            response_type_warning = self._response_type_warning(normalized.response_type, public_surface=False)
            if response_type_warning is not None:
                warnings.append(response_type_warning)
        return {
            "id": f"msg-{uuid4().hex[:8]}",
            "role": "assistant",
            "content": (
                "Tôi chưa tìm thấy ngữ cảnh phù hợp trong kho tri thức hiện tại. Bạn nên diễn đạt cụ thể hơn hoặc đối chiếu với đơn vị phụ trách."
                if no_context
                else raw_response
            ),
            "created_at": utc_now_iso(),
            "confidence": self._live_chat_confidence(
                normalized.response_type,
                reference_count=len(references),
                no_context=no_context,
                public_surface=False,
            ),
            "references": references,
            "warnings": warnings,
        }

    def _build_public_live_chat_reply_legacy(self, question: str, conversation: dict | None) -> dict:
        self._ensure_public_workspace_seeded()
        self._wait_for_public_workspace_ready()
        retrieval_query = question
        result = get_public_lightrag_client().query_text(
            retrieval_query,
            conversation_history=self._build_chat_conversation_history(conversation),
            mode="mix",
            include_references=True,
            include_chunk_content=True,
            response_type="Multiple Paragraphs",
        )
        if result.get("error"):
            return self._build_public_catalog_chat_reply(question)

        normalized = normalize_chat_result(result)
        raw_response = self._sanitize_lightrag_response_text(normalized.response_text)
        references = [self._build_public_live_reference(reference) for reference in normalized.references]
        no_context = normalized.no_context or not references
        if no_context:
            self._force_public_workspace_reseed()
            result = get_public_lightrag_client().query_text(
                retrieval_query,
                conversation_history=self._build_chat_conversation_history(conversation),
                mode="mix",
                include_references=True,
                include_chunk_content=True,
                response_type="Multiple Paragraphs",
            )
            if result.get("error"):
                return self._build_public_catalog_chat_reply(question)

            normalized = normalize_chat_result(result)
            raw_response = self._sanitize_lightrag_response_text(normalized.response_text)
            references = [self._build_public_live_reference(reference) for reference in normalized.references]
            no_context = normalized.no_context or not references
            if no_context:
                return self._build_public_catalog_chat_reply(question)

        references, ranked_reference_documents = self._filter_references_for_chat(references, question)
        if not self._references_have_strong_grounding(ranked_reference_documents, question):
            return self._build_low_grounding_chat_reply(
                question,
                references,
                public_surface=True,
                ranked_reference_documents=ranked_reference_documents,
            )

        warnings: list[dict] = []
        response_type_warning = self._response_type_warning(normalized.response_type, public_surface=True)
        if response_type_warning is not None:
            warnings.append(response_type_warning)

        return {
            "id": f"msg-{uuid4().hex[:8]}",
            "role": "assistant",
            "content": self._select_public_live_answer_content(
                question,
                raw_response,
                references,
                ranked_reference_documents,
            ),
            "created_at": utc_now_iso(),
            "confidence": self._live_chat_confidence(
                normalized.response_type,
                reference_count=len(references),
                no_context=False,
                public_surface=True,
            ),
            "references": references,
            "warnings": warnings,
        }

    def _build_live_chat_reply(self, question: str, conversation: dict | None) -> dict:
        self._ensure_internal_workspace_seeded()
        self._wait_for_internal_workspace_ready()
        result = self._query_internal_live_chat_result(question, conversation)
        if result.get("error"):
            self._raise(502, "live_query_failed", "Live chat query failed while generating the answer.")

        normalized = normalize_chat_result(result)
        raw_response = self._sanitize_lightrag_response_text(normalized.response_text)
        references = [self._build_live_reference(reference) for reference in normalized.references]
        no_context = normalized.no_context or not references
        if no_context:
            self._force_internal_workspace_reseed()
            result = self._query_internal_live_chat_result(question, conversation)
            if result.get("error"):
                self._raise(502, "live_query_failed", "Live chat query failed while generating the answer.")
            normalized = normalize_chat_result(result)
            raw_response = self._sanitize_lightrag_response_text(normalized.response_text)
            references = [self._build_live_reference(reference) for reference in normalized.references]
            no_context = normalized.no_context or not references

        references, ranked_reference_documents = self._filter_references_for_chat(references, question)
        if no_context or not self._references_have_strong_grounding(ranked_reference_documents, question):
            return self._build_low_grounding_chat_reply(
                question,
                references,
                public_surface=False,
                ranked_reference_documents=ranked_reference_documents,
            )

        warnings: list[dict] = []
        response_type_warning = self._response_type_warning(normalized.response_type, public_surface=False)
        if response_type_warning is not None:
            warnings.append(response_type_warning)

        top_document = ranked_reference_documents[0]["document"] if ranked_reference_documents else None
        final_content = self._build_temporal_validity_answer(question, top_document) or raw_response

        return {
            "id": f"msg-{uuid4().hex[:8]}",
            "role": "assistant",
            "content": final_content,
            "created_at": utc_now_iso(),
            "confidence": self._live_chat_confidence(
                normalized.response_type,
                reference_count=len(references),
                no_context=False,
                public_surface=False,
            ),
            "references": references,
            "warnings": warnings,
        }

    def _build_public_live_chat_reply(self, question: str, conversation: dict | None) -> dict:
        self._ensure_public_workspace_seeded()
        self._wait_for_public_workspace_ready()
        result = self._query_public_live_chat_result(question, conversation)
        if result.get("error"):
            return self._build_public_catalog_chat_reply(question)

        normalized = normalize_chat_result(result)
        raw_response = self._sanitize_lightrag_response_text(normalized.response_text)
        references = [self._build_public_live_reference(reference) for reference in normalized.references]
        no_context = normalized.no_context or not references
        if no_context:
            self._force_public_workspace_reseed()
            result = self._query_public_live_chat_result(question, conversation)
            if result.get("error"):
                return self._build_public_catalog_chat_reply(question)

            normalized = normalize_chat_result(result)
            raw_response = self._sanitize_lightrag_response_text(normalized.response_text)
            references = [self._build_public_live_reference(reference) for reference in normalized.references]
            no_context = normalized.no_context or not references
            if no_context:
                return self._build_public_catalog_chat_reply(question)

        references, ranked_reference_documents = self._filter_references_for_chat(references, question)
        if not self._references_have_strong_grounding(ranked_reference_documents, question):
            return self._build_low_grounding_chat_reply(
                question,
                references,
                public_surface=True,
                ranked_reference_documents=ranked_reference_documents,
            )

        warnings: list[dict] = []
        response_type_warning = self._response_type_warning(normalized.response_type, public_surface=True)
        if response_type_warning is not None:
            warnings.append(response_type_warning)

        final_content = self._select_public_live_answer_content(
            question,
            raw_response,
            references,
            ranked_reference_documents,
        )

        return {
            "id": f"msg-{uuid4().hex[:8]}",
            "role": "assistant",
            "content": final_content,
            "created_at": utc_now_iso(),
            "confidence": self._live_chat_confidence(
                normalized.response_type,
                reference_count=len(references),
                no_context=False,
                public_surface=True,
            ),
            "references": references,
            "warnings": warnings,
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

    def _upsert_chat_conversation(
        self,
        conversation_id: str,
        question: str,
        reply: dict,
        existing_conversation: dict | None,
        owner_key: str | None,
    ) -> None:
        if owner_key is None:
            return
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
                "owner_key": owner_key,
                "title": question[:64] or "Cuộc trò chuyện mới",
                "updated_at": reply["created_at"],
                "messages": [user_message, deepcopy(reply)],
            }
        )

    def _build_persisted_live_chat_reply(
        self,
        question: str,
        result: dict,
        *,
        public_surface: bool,
    ) -> dict:
        normalized = normalize_chat_result(result)
        raw_response = self._sanitize_lightrag_response_text(normalized.response_text)
        references = [
            self._build_public_live_reference(reference) if public_surface else self._build_live_reference(reference)
            for reference in normalized.references
        ]
        no_context = normalized.no_context
        has_references = bool(references)

        if public_surface and no_context:
            return self._build_public_catalog_chat_reply(question)

        references, ranked_reference_documents = self._filter_references_for_chat(references, question)
        has_strong_grounding = self._references_have_strong_grounding(ranked_reference_documents, question)
        weak_grounding = (not has_references) or (not has_strong_grounding)
        preserve_live_answer = bool(raw_response) and not no_context

        if (no_context or weak_grounding) and not preserve_live_answer:
            return self._build_low_grounding_chat_reply(
                question,
                references,
                public_surface=public_surface,
                ranked_reference_documents=ranked_reference_documents,
            )

        warnings: list[dict] = []
        response_type_warning = self._response_type_warning(normalized.response_type, public_surface=public_surface)
        if response_type_warning is not None:
            warnings.append(response_type_warning)

        if weak_grounding:
            # The live stream has already produced an answer; keep it visible and
            # surface the grounding weakness as a warning instead of replacing the
            # answer with a generic fallback summary.
            warnings.append(
                {
                    "code": "insufficient_grounding",
                    "message": (
                        "Nguon truy xuat hien moi dung o muc lien quan, chua du manh de xac nhan truc tiep cau tra loi."
                    ),
                }
            )
            final_content = raw_response
            confidence = 0.52 if public_surface else 0.46
        else:
            if public_surface:
                final_content = self._select_public_live_answer_content(
                    question,
                    raw_response,
                    references,
                    ranked_reference_documents,
                )
            else:
                top_document = ranked_reference_documents[0]["document"] if ranked_reference_documents else None
                final_content = self._build_temporal_validity_answer(question, top_document) or raw_response
            confidence = self._live_chat_confidence(
                normalized.response_type,
                reference_count=len(references),
                no_context=False,
                public_surface=public_surface,
            )

        return {
            "id": f"msg-{uuid4().hex[:8]}",
            "role": "assistant",
            "content": final_content,
            "created_at": utc_now_iso(),
            "confidence": confidence,
            "references": references,
            "warnings": warnings,
        }

    def persist_live_chat_message(
        self,
        payload: dict,
        scenario: str,
        role: Role = "guest",
        session: dict | None = None,
        session_token: str | None = None,
    ) -> dict:
        del scenario

        question = str(payload.get("message") or "").strip() or "Bạn có thể nói rõ hơn yêu cầu không?"
        raw_result = payload.get("result")
        if not isinstance(raw_result, dict) or not raw_result:
            self._raise(422, "live_result_invalid", "Live stream result is missing or invalid.")

        conversation_id = payload.get("conversationId") or f"conv-{uuid4().hex[:8]}"
        owner_key = self._conversation_owner_key(role, session, session_token)
        owner_aliases = self._conversation_owner_aliases(role, session, session_token)
        raw_conversation = self.store.get_conversation_by_id(conversation_id)
        if raw_conversation is not None:
            raw_conversation = self._ensure_conversation_owner(raw_conversation, owner_key, owner_aliases)
        if raw_conversation is not None and not self._conversation_visible_to_owner(raw_conversation, owner_key, owner_aliases):
            self._raise(404, "conversation_not_found", "Không tìm thấy cuộc trò chuyện.")

        reply = self._build_persisted_live_chat_reply(
            question,
            raw_result,
            public_surface=not self._is_document_admin(role),
        )
        reply = {**reply, "content": self._sanitize_chat_message_content(reply.get("content", ""))}
        self._upsert_chat_conversation(conversation_id, question, reply, raw_conversation, owner_key)

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

    def send_chat_message(
        self,
        payload: dict,
        scenario: str,
        role: Role = "guest",
        session: dict | None = None,
        session_token: str | None = None,
    ) -> dict:
        if scenario == "error":
            self._raise(500, "chat_failed", "Unable to generate assistant response.")

        question = payload.get("message") or "Bạn có thể nói rõ hơn yêu cầu không?"
        conversation_id = payload.get("conversationId") or f"conv-{uuid4().hex[:8]}"
        owner_key = self._conversation_owner_key(role, session, session_token)
        owner_aliases = self._conversation_owner_aliases(role, session, session_token)
        raw_conversation = self.store.get_conversation_by_id(conversation_id)
        if raw_conversation is not None:
            raw_conversation = self._ensure_conversation_owner(raw_conversation, owner_key, owner_aliases)
        if raw_conversation is not None and not self._conversation_visible_to_owner(raw_conversation, owner_key, owner_aliases):
            self._raise(404, "conversation_not_found", "Không tìm thấy cuộc trò chuyện.")
        existing_conversation = raw_conversation
        if self._should_use_live_chat(role, scenario):
            try:
                reply = self._build_live_chat_reply(question, existing_conversation)
            except ApiServiceError as exc:
                if exc.status_code != 502:
                    raise
                fallback_reply = self._build_mock_chat_reply(question, scenario)
                fallback_warnings = list(fallback_reply.get("warnings", []))
                fallback_warnings.append(
                    {
                        "code": "live_backend_unavailable",
                        "message": "Kho tri thuc live tam thoi chua san sang. /web dang tra ve phan hoi du phong de giao dien tiep tuc hoat dong.",
                    }
                )
                reply = {
                    **fallback_reply,
                    "content": f'Kho tri thuc live tam thoi chua san sang. Dang tra ve phan hoi du phong. {fallback_reply["content"]}',
                    "confidence": 0.24,
                    "warnings": fallback_warnings,
                }
        elif self._should_use_public_live_chat(role, scenario):
            reply = self._build_public_live_chat_reply(question, existing_conversation)
        elif self._should_use_public_catalog_chat(role, scenario):
            reply = self._build_public_catalog_chat_reply(question)
        else:
            reply = self._build_mock_chat_reply(question, scenario)
        reply = {**reply, "content": self._sanitize_chat_message_content(reply.get("content", ""))}
        self._upsert_chat_conversation(conversation_id, question, reply, existing_conversation, owner_key)
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
