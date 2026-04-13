"""SQLAlchemy-backed persistence for the /web workspace state."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Protocol, TypedDict

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, create_engine, delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.sql import func

from api.services.fixtures import build_initial_state


class WorkspaceState(TypedDict):
    sessions: dict[str, dict]
    issued_session_tokens: dict[str, dict]
    pending_sso_states: dict[str, dict]
    documents: list[dict]
    submissions: list[dict]
    reviews: list[dict]
    jobs: list[dict]
    admin_users: list[dict]
    role_policies: list[dict]
    system_settings: list[dict]
    audit_logs: list[dict]
    dense_audit_logs: list[dict]
    conversations: list[dict]


NORMALIZED_STATE_KEYS: tuple[str, ...] = (
    "sessions",
    "issued_session_tokens",
    "pending_sso_states",
    "documents",
    "submissions",
    "reviews",
    "jobs",
    "admin_users",
    "role_policies",
    "system_settings",
    "audit_logs",
    "dense_audit_logs",
    "conversations",
)
LEGACY_BLOB_FALLBACK_KEYS: tuple[str, ...] = NORMALIZED_STATE_KEYS
BLOB_STATE_KEYS: tuple[str, ...] = ()
STATE_KEYS: tuple[str, ...] = NORMALIZED_STATE_KEYS + BLOB_STATE_KEYS


def build_seed_state() -> WorkspaceState:
    return {
        **deepcopy(build_initial_state()),
        "issued_session_tokens": {},
        "pending_sso_states": {},
    }


class WorkspaceStateStore(Protocol):
    def get_state(self) -> WorkspaceState: ...

    def reset(self) -> WorkspaceState: ...

    def save_state(self, state: WorkspaceState) -> WorkspaceState: ...

    def upsert_pending_sso_state(self, state: str, payload: dict) -> dict: ...

    def consume_pending_sso_state(self, state: str) -> dict | None: ...

    def update_system_setting_value(self, key: str, value: str) -> dict | None: ...

    def upsert_conversation(self, conversation: dict) -> dict: ...

    def dispose(self) -> None: ...

    # ── Per-entity CRUD (repository pattern) ──

    # Session templates
    def get_session_templates(self) -> dict[str, dict]: ...

    # Issued session tokens
    def get_issued_session_token(self, token: str) -> dict | None: ...
    def create_issued_session_token(self, token: str, payload: dict) -> None: ...
    def delete_issued_session_token(self, token: str) -> None: ...

    # Pending SSO states
    def get_pending_sso_states(self) -> dict[str, dict]: ...

    # Documents
    def get_document_by_id(self, doc_id: str) -> dict | None: ...
    def list_all_documents(self) -> list[dict]: ...
    def create_document(self, doc: dict) -> dict: ...
    def update_document_payload(self, doc_id: str, doc: dict) -> dict: ...

    # Submissions
    def get_submission_by_id(self, sub_id: str) -> dict | None: ...
    def list_all_submissions(self) -> list[dict]: ...
    def create_submission(self, sub: dict) -> dict: ...
    def update_submission_payload(self, sub_id: str, sub: dict) -> dict: ...

    # Reviews
    def get_review_by_id(self, review_id: str) -> dict | None: ...
    def list_all_reviews(self) -> list[dict]: ...
    def create_review(self, review: dict) -> dict: ...
    def update_review_payload(self, review_id: str, review: dict) -> dict: ...

    # Jobs
    def get_job_by_id(self, job_id: str) -> dict | None: ...
    def list_all_jobs(self) -> list[dict]: ...
    def create_job(self, job: dict) -> dict: ...
    def update_job_payload(self, job_id: str, job: dict) -> dict: ...

    # Admin users
    def get_admin_user_by_id(self, user_id: str) -> dict | None: ...
    def get_admin_user_by_email(self, email: str) -> dict | None: ...
    def list_all_admin_users(self) -> list[dict]: ...
    def upsert_admin_user(self, user: dict) -> dict: ...
    def update_admin_user_payload(self, user_id: str, user: dict) -> dict: ...

    # Role policies
    def list_all_role_policies(self) -> list[dict]: ...

    # System settings
    def list_all_system_settings(self) -> list[dict]: ...

    # Audit logs
    def list_all_audit_logs(self) -> list[dict]: ...
    def create_audit_log(self, entry: dict) -> dict: ...
    def list_all_dense_audit_logs(self) -> list[dict]: ...

    # Conversations
    def list_all_conversations(self) -> list[dict]: ...
    def get_conversation_by_id(self, conv_id: str) -> dict | None: ...


class Base(DeclarativeBase):
    pass


class WorkspaceStateEntry(Base):
    __tablename__ = "workspace_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkspaceSessionTemplate(Base):
    __tablename__ = "workspace_session_templates"

    role: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    session_status: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    user_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_department: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_initials: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkspaceIssuedSessionToken(Base):
    __tablename__ = "workspace_issued_session_tokens"

    token: Mapped[str] = mapped_column(String(255), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    auth_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkspacePendingSsoState(Base):
    __tablename__ = "workspace_pending_sso_states"

    state: Mapped[str] = mapped_column(String(255), primary_key=True)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False)
    return_to: Mapped[str] = mapped_column(Text, nullable=False)
    created_at_iso: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkspaceRolePolicy(Base):
    __tablename__ = "workspace_role_policies"

    role: Mapped[str] = mapped_column(String(32), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    requires_internal_email: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkspaceAdminUser(Base):
    __tablename__ = "workspace_admin_users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    last_active_at_iso: Mapped[str] = mapped_column(String(64), nullable=False)
    is_internal_domain_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkspaceSubmission(Base):
    __tablename__ = "workspace_submissions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False)
    linked_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    visibility_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at_iso: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at_iso: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkspaceReview(Base):
    __tablename__ = "workspace_reviews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    submission_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    published_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    visibility_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reviewer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at_iso: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkspaceSystemSetting(Base):
    __tablename__ = "workspace_system_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    group_name: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkspaceJob(Base):
    __tablename__ = "workspace_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    progress: Mapped[float] = mapped_column(Float, nullable=False)
    related_title: Mapped[str] = mapped_column(Text, nullable=False)
    started_at_iso: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at_iso: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkspaceAuditLog(Base):
    __tablename__ = "workspace_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_label: Mapped[str] = mapped_column(Text, nullable=False)
    created_at_iso: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkspaceDenseAuditLog(Base):
    __tablename__ = "workspace_dense_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_label: Mapped[str] = mapped_column(Text, nullable=False)
    created_at_iso: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkspaceDocument(Base):
    __tablename__ = "workspace_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    owner_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False)
    visibility_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at_iso: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at_iso: Mapped[str] = mapped_column(String(64), nullable=False)
    indexed_at_iso: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkspaceConversation(Base):
    __tablename__ = "workspace_conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at_iso: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class SqlAlchemyWorkspaceStore:
    """Persists workspace state with normalized SQLAlchemy tables for primary domains."""

    def __init__(self, *, database_url: str, auto_seed: bool = True) -> None:
        self.database_url = database_url
        self.auto_seed = auto_seed
        self.is_sqlite = database_url.startswith("sqlite")
        self._ensure_sqlite_parent_exists(database_url)
        self.engine = create_engine(database_url, future=True)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, class_=Session)
        # For SQLite: create tables directly (Alembic not required).
        # For Postgres: tables are managed by Alembic migrations.
        if self.is_sqlite:
            Base.metadata.create_all(self.engine)
        if self.auto_seed:
            self._ensure_seeded()

    def _ensure_sqlite_parent_exists(self, database_url: str) -> None:
        url = make_url(database_url)
        if not url.drivername.startswith("sqlite") or not url.database or url.database in {":memory:"}:
            return

        Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

    def _has_any_persisted_state(self, session: Session) -> bool:
        if session.scalar(select(func.count()).select_from(WorkspaceStateEntry)) or 0:
            return True
        for model in (
            WorkspaceSessionTemplate,
            WorkspaceIssuedSessionToken,
            WorkspacePendingSsoState,
            WorkspaceRolePolicy,
            WorkspaceAdminUser,
            WorkspaceSubmission,
            WorkspaceReview,
            WorkspaceSystemSetting,
            WorkspaceJob,
            WorkspaceAuditLog,
            WorkspaceDenseAuditLog,
            WorkspaceDocument,
            WorkspaceConversation,
        ):
            if session.scalar(select(func.count()).select_from(model)) or 0:
                return True
        return False

    def _normalized_table_counts(self, session: Session) -> dict[str, int]:
        return {
            "sessions": session.scalar(select(func.count()).select_from(WorkspaceSessionTemplate)) or 0,
            "issued_session_tokens": session.scalar(select(func.count()).select_from(WorkspaceIssuedSessionToken)) or 0,
            "pending_sso_states": session.scalar(select(func.count()).select_from(WorkspacePendingSsoState)) or 0,
            "role_policies": session.scalar(select(func.count()).select_from(WorkspaceRolePolicy)) or 0,
            "admin_users": session.scalar(select(func.count()).select_from(WorkspaceAdminUser)) or 0,
            "submissions": session.scalar(select(func.count()).select_from(WorkspaceSubmission)) or 0,
            "reviews": session.scalar(select(func.count()).select_from(WorkspaceReview)) or 0,
            "system_settings": session.scalar(select(func.count()).select_from(WorkspaceSystemSetting)) or 0,
            "jobs": session.scalar(select(func.count()).select_from(WorkspaceJob)) or 0,
            "audit_logs": session.scalar(select(func.count()).select_from(WorkspaceAuditLog)) or 0,
            "dense_audit_logs": session.scalar(select(func.count()).select_from(WorkspaceDenseAuditLog)) or 0,
            "documents": session.scalar(select(func.count()).select_from(WorkspaceDocument)) or 0,
            "conversations": session.scalar(select(func.count()).select_from(WorkspaceConversation)) or 0,
        }

    def _load_blob_rows(self, session: Session) -> dict[str, WorkspaceStateEntry]:
        rows = session.scalars(select(WorkspaceStateEntry).where(WorkspaceStateEntry.key.in_(STATE_KEYS))).all()
        return {row.key: row for row in rows}

    def _should_migrate_legacy_blobs(
        self,
        blob_rows: dict[str, WorkspaceStateEntry],
        normalized_counts: dict[str, int],
    ) -> bool:
        return any(key in blob_rows and normalized_counts[key] == 0 for key in LEGACY_BLOB_FALLBACK_KEYS)

    def _ensure_seeded(self) -> None:
        with self.session_factory() as session:
            if not self._has_any_persisted_state(session):
                self.save_state(build_seed_state())
                return

            blob_rows = self._load_blob_rows(session)
            normalized_counts = self._normalized_table_counts(session)

        if self._should_migrate_legacy_blobs(blob_rows, normalized_counts):
            self.save_state(self._load_state())

    def _load_sessions(
        self,
        session: Session,
        *,
        blob_rows: dict[str, WorkspaceStateEntry],
        seed: WorkspaceState,
    ) -> dict[str, dict]:
        rows = session.scalars(select(WorkspaceSessionTemplate).order_by(WorkspaceSessionTemplate.role.asc())).all()
        if rows:
            return {row.role: deepcopy(row.payload) for row in rows}
        if "sessions" in blob_rows:
            return deepcopy(blob_rows["sessions"].payload)
        return deepcopy(seed["sessions"])

    def _load_issued_session_tokens(
        self,
        session: Session,
        *,
        blob_rows: dict[str, WorkspaceStateEntry],
        seed: WorkspaceState,
    ) -> dict[str, dict]:
        rows = session.scalars(select(WorkspaceIssuedSessionToken)).all()
        if rows:
            tokens: dict[str, dict] = {}
            for row in rows:
                token_payload: dict[str, object] = {"role": row.role}
                if row.auth_method is not None:
                    token_payload["auth_method"] = row.auth_method
                if row.session_payload is not None:
                    token_payload["session"] = deepcopy(row.session_payload)
                tokens[row.token] = token_payload
            return tokens
        if "issued_session_tokens" in blob_rows:
            return deepcopy(blob_rows["issued_session_tokens"].payload)
        return deepcopy(seed["issued_session_tokens"])

    def _load_ordered_payloads(
        self,
        session: Session,
        model,
        *,
        key: str,
        blob_rows: dict[str, WorkspaceStateEntry],
        seed: WorkspaceState,
    ) -> list[dict]:
        rows = session.scalars(select(model).order_by(model.position.asc())).all()
        if rows:
            return [deepcopy(row.payload) for row in rows]
        if key in blob_rows:
            return deepcopy(blob_rows[key].payload)
        return deepcopy(seed[key])

    def _load_pending_sso_states(
        self,
        session: Session,
        *,
        blob_rows: dict[str, WorkspaceStateEntry],
        seed: WorkspaceState,
    ) -> dict[str, dict]:
        rows = session.scalars(select(WorkspacePendingSsoState).order_by(WorkspacePendingSsoState.state.asc())).all()
        if rows:
            return {row.state: deepcopy(row.payload) for row in rows}
        if "pending_sso_states" in blob_rows:
            return deepcopy(blob_rows["pending_sso_states"].payload)
        return deepcopy(seed["pending_sso_states"])

    def _load_blob_payload(
        self,
        *,
        key: str,
        blob_rows: dict[str, WorkspaceStateEntry],
        seed: WorkspaceState,
    ) -> dict[str, dict] | list[dict]:
        if key in blob_rows:
            return deepcopy(blob_rows[key].payload)
        return deepcopy(seed[key])

    def _load_state(self) -> WorkspaceState:
        seed = build_seed_state()
        with self.session_factory() as session:
            blob_rows = self._load_blob_rows(session)
            return {
                "sessions": self._load_sessions(session, blob_rows=blob_rows, seed=seed),
                "issued_session_tokens": self._load_issued_session_tokens(session, blob_rows=blob_rows, seed=seed),
                "pending_sso_states": self._load_pending_sso_states(session, blob_rows=blob_rows, seed=seed),
                "documents": self._load_ordered_payloads(
                    session,
                    WorkspaceDocument,
                    key="documents",
                    blob_rows=blob_rows,
                    seed=seed,
                ),
                "submissions": self._load_ordered_payloads(
                    session,
                    WorkspaceSubmission,
                    key="submissions",
                    blob_rows=blob_rows,
                    seed=seed,
                ),
                "reviews": self._load_ordered_payloads(
                    session,
                    WorkspaceReview,
                    key="reviews",
                    blob_rows=blob_rows,
                    seed=seed,
                ),
                "jobs": self._load_ordered_payloads(
                    session,
                    WorkspaceJob,
                    key="jobs",
                    blob_rows=blob_rows,
                    seed=seed,
                ),
                "admin_users": self._load_ordered_payloads(
                    session,
                    WorkspaceAdminUser,
                    key="admin_users",
                    blob_rows=blob_rows,
                    seed=seed,
                ),
                "role_policies": self._load_ordered_payloads(
                    session,
                    WorkspaceRolePolicy,
                    key="role_policies",
                    blob_rows=blob_rows,
                    seed=seed,
                ),
                "system_settings": self._load_ordered_payloads(
                    session,
                    WorkspaceSystemSetting,
                    key="system_settings",
                    blob_rows=blob_rows,
                    seed=seed,
                ),
                "audit_logs": self._load_ordered_payloads(
                    session,
                    WorkspaceAuditLog,
                    key="audit_logs",
                    blob_rows=blob_rows,
                    seed=seed,
                ),
                "dense_audit_logs": self._load_ordered_payloads(
                    session,
                    WorkspaceDenseAuditLog,
                    key="dense_audit_logs",
                    blob_rows=blob_rows,
                    seed=seed,
                ),
                "conversations": self._load_ordered_payloads(
                    session,
                    WorkspaceConversation,
                    key="conversations",
                    blob_rows=blob_rows,
                    seed=seed,
                ),
            }

    def get_state(self) -> WorkspaceState:
        return self._load_state()

    def _replace_blob_payloads(self, session: Session, state: WorkspaceState) -> None:
        existing_keys = set(session.scalars(select(WorkspaceStateEntry.key)).all())
        stale_keys = existing_keys - set(BLOB_STATE_KEYS)
        if stale_keys:
            session.execute(delete(WorkspaceStateEntry).where(WorkspaceStateEntry.key.in_(stale_keys)))

        for key in BLOB_STATE_KEYS:
            payload = deepcopy(state[key])
            existing = session.get(WorkspaceStateEntry, key)
            if existing is None:
                session.add(WorkspaceStateEntry(key=key, payload=payload))
            else:
                existing.payload = payload

    def _replace_session_templates(self, session: Session, templates: dict[str, dict]) -> None:
        existing_roles = set(session.scalars(select(WorkspaceSessionTemplate.role)).all())
        target_roles = set(templates)
        stale_roles = existing_roles - target_roles
        if stale_roles:
            session.execute(delete(WorkspaceSessionTemplate).where(WorkspaceSessionTemplate.role.in_(stale_roles)))

        for role, payload in templates.items():
            user = payload["user"]
            row = session.get(WorkspaceSessionTemplate, role)
            values = {
                "role": role,
                "session_id": payload["session_id"],
                "session_status": payload["status"],
                "user_id": user["id"],
                "user_email": user["email"],
                "user_name": user["name"],
                "user_department": user["department"],
                "avatar_initials": user["avatar_initials"],
                "payload": deepcopy(payload),
            }
            if row is None:
                session.add(WorkspaceSessionTemplate(**values))
                continue
            row.session_id = values["session_id"]
            row.session_status = values["session_status"]
            row.user_id = values["user_id"]
            row.user_email = values["user_email"]
            row.user_name = values["user_name"]
            row.user_department = values["user_department"]
            row.avatar_initials = values["avatar_initials"]
            row.payload = values["payload"]

    def _replace_issued_session_tokens(self, session: Session, tokens: dict[str, dict]) -> None:
        existing_tokens = set(session.scalars(select(WorkspaceIssuedSessionToken.token)).all())
        target_tokens = set(tokens)
        stale_tokens = existing_tokens - target_tokens
        if stale_tokens:
            session.execute(delete(WorkspaceIssuedSessionToken).where(WorkspaceIssuedSessionToken.token.in_(stale_tokens)))

        for token, payload in tokens.items():
            if isinstance(payload, str):
                role = payload
                auth_method = None
                session_payload = None
            else:
                role = payload.get("role", "guest")
                auth_method = payload.get("auth_method")
                session_payload = deepcopy(payload.get("session"))
            row = session.get(WorkspaceIssuedSessionToken, token)
            values = {
                "token": token,
                "role": role,
                "auth_method": auth_method,
                "session_payload": session_payload,
            }
            if row is None:
                session.add(WorkspaceIssuedSessionToken(**values))
                continue
            row.role = values["role"]
            row.auth_method = values["auth_method"]
            row.session_payload = values["session_payload"]

    def _replace_pending_sso_states(self, session: Session, pending_states: dict[str, dict]) -> None:
        existing_states = set(session.scalars(select(WorkspacePendingSsoState.state)).all())
        target_states = set(pending_states)
        stale_states = existing_states - target_states
        if stale_states:
            session.execute(delete(WorkspacePendingSsoState).where(WorkspacePendingSsoState.state.in_(stale_states)))

        for state, payload in pending_states.items():
            row = session.get(WorkspacePendingSsoState, state)
            values = {
                "state": state,
                "scenario": payload.get("scenario", "happy"),
                "return_to": payload.get("return_to", ""),
                "created_at_iso": payload.get("created_at", ""),
                "payload": deepcopy(payload),
            }
            if row is None:
                session.add(WorkspacePendingSsoState(**values))
                continue
            row.scenario = values["scenario"]
            row.return_to = values["return_to"]
            row.created_at_iso = values["created_at_iso"]
            row.payload = values["payload"]

    def _replace_ordered_rows(
        self,
        session: Session,
        model,
        items: list[dict],
        row_factory,
        *,
        primary_key_attr: str = "id",
        item_key_name: str = "id",
    ) -> None:
        primary_key_column = getattr(model, primary_key_attr)
        target_ids = {item[item_key_name] for item in items}
        existing_ids = set(session.scalars(select(primary_key_column)).all())
        stale_ids = existing_ids - target_ids
        if stale_ids:
            session.execute(delete(model).where(primary_key_column.in_(stale_ids)))

        for position, item in enumerate(items):
            row_id, values = row_factory(item, position)
            row = session.get(model, row_id)
            if row is None:
                session.add(model(**values))
                continue
            for key, value in values.items():
                setattr(row, key, value)

    def _replace_admin_users(self, session: Session, users: list[dict]) -> None:
        def make_row(user: dict, position: int) -> tuple[str, dict]:
            return user["id"], {
                "id": user["id"],
                "position": position,
                "email": user["email"],
                "role": user["role"],
                "status": user["status"],
                "scope": user["scope"],
                "last_active_at_iso": user["last_active_at"],
                "is_internal_domain_compliant": bool(user["is_internal_domain_compliant"]),
                "payload": deepcopy(user),
            }

        self._replace_ordered_rows(session, WorkspaceAdminUser, users, make_row)

    def _replace_role_policies(self, session: Session, role_policies: list[dict]) -> None:
        def make_row(policy: dict, position: int) -> tuple[str, dict]:
            return policy["role"], {
                "role": policy["role"],
                "position": position,
                "requires_internal_email": bool(policy["requires_internal_email"]),
                "payload": deepcopy(policy),
            }

        self._replace_ordered_rows(
            session,
            WorkspaceRolePolicy,
            role_policies,
            make_row,
            primary_key_attr="role",
            item_key_name="role",
        )

    def _replace_submissions(self, session: Session, submissions: list[dict]) -> None:
        def make_row(submission: dict, position: int) -> tuple[str, dict]:
            return submission["id"], {
                "id": submission["id"],
                "position": position,
                "title": submission["title"],
                "source_type": submission["source_type"],
                "lifecycle_status": submission["lifecycle_status"],
                "processing_status": submission["processing_status"],
                "linked_document_id": submission.get("linked_document_id"),
                "visibility_scope": submission["supplemental_metadata"]["visibility_scope"],
                "created_at_iso": submission["created_at"],
                "updated_at_iso": submission["updated_at"],
                "payload": deepcopy(submission),
            }

        self._replace_ordered_rows(session, WorkspaceSubmission, submissions, make_row)

    def _replace_reviews(self, session: Session, reviews: list[dict]) -> None:
        def make_row(review: dict, position: int) -> tuple[str, dict]:
            return review["id"], {
                "id": review["id"],
                "position": position,
                "submission_id": review["submission_id"],
                "published_document_id": review.get("published_document_id"),
                "title": review["title"],
                "source_type": review["source_type"],
                "visibility_scope": review["visibility_scope"],
                "status": review["status"],
                "confidence": float(review["confidence"]),
                "reviewer_name": review["reviewer_name"],
                "created_at_iso": review["created_at"],
                "payload": deepcopy(review),
            }

        self._replace_ordered_rows(session, WorkspaceReview, reviews, make_row)

    def _replace_system_settings(self, session: Session, settings: list[dict]) -> None:
        def make_row(setting: dict, position: int) -> tuple[str, dict]:
            return setting["key"], {
                "key": setting["key"],
                "position": position,
                "group_name": setting["group"],
                "label": setting["label"],
                "value": setting["value"],
                "is_sensitive": bool(setting["is_sensitive"]),
                "source": setting["source"],
                "payload": deepcopy(setting),
            }

        self._replace_ordered_rows(
            session,
            WorkspaceSystemSetting,
            settings,
            make_row,
            primary_key_attr="key",
            item_key_name="key",
        )

    def _replace_jobs(self, session: Session, jobs: list[dict]) -> None:
        def make_row(job: dict, position: int) -> tuple[str, dict]:
            return job["id"], {
                "id": job["id"],
                "position": position,
                "job_type": job["type"],
                "status": job["status"],
                "progress": float(job["progress"]),
                "related_title": job["related_title"],
                "started_at_iso": job["started_at"],
                "updated_at_iso": job["updated_at"],
                "payload": deepcopy(job),
            }

        self._replace_ordered_rows(session, WorkspaceJob, jobs, make_row)

    def _replace_audit_logs(self, session: Session, audit_logs: list[dict]) -> None:
        def make_row(log: dict, position: int) -> tuple[str, dict]:
            return log["id"], {
                "id": log["id"],
                "position": position,
                "actor_name": log["actor_name"],
                "actor_role": log["actor_role"],
                "action": log["action"],
                "target_type": log["target_type"],
                "target_id": log["target_id"],
                "target_label": log["target_label"],
                "created_at_iso": log["created_at"],
                "payload": deepcopy(log),
            }

        self._replace_ordered_rows(session, WorkspaceAuditLog, audit_logs, make_row)

    def _replace_dense_audit_logs(self, session: Session, audit_logs: list[dict]) -> None:
        def make_row(log: dict, position: int) -> tuple[str, dict]:
            return log["id"], {
                "id": log["id"],
                "position": position,
                "actor_name": log["actor_name"],
                "actor_role": log["actor_role"],
                "action": log["action"],
                "target_type": log["target_type"],
                "target_id": log["target_id"],
                "target_label": log["target_label"],
                "created_at_iso": log["created_at"],
                "payload": deepcopy(log),
            }

        self._replace_ordered_rows(session, WorkspaceDenseAuditLog, audit_logs, make_row)

    def _replace_documents(self, session: Session, documents: list[dict]) -> None:
        def make_row(document: dict, position: int) -> tuple[str, dict]:
            system_metadata = document["system_metadata"]
            supplemental_metadata = document["supplemental_metadata"]
            return document["id"], {
                "id": document["id"],
                "position": position,
                "title": document["title"],
                "owner_email": document["owner_email"],
                "lifecycle_status": document["lifecycle_status"],
                "processing_status": document["processing_status"],
                "visibility_scope": supplemental_metadata["visibility_scope"],
                "is_archived": bool(system_metadata["is_archived"]),
                "created_at_iso": document["created_at"],
                "updated_at_iso": document["updated_at"],
                "indexed_at_iso": system_metadata.get("indexed_at"),
                "payload": deepcopy(document),
            }

        self._replace_ordered_rows(session, WorkspaceDocument, documents, make_row)

    def _replace_conversations(self, session: Session, conversations: list[dict]) -> None:
        def make_row(conversation: dict, position: int) -> tuple[str, dict]:
            return conversation["id"], {
                "id": conversation["id"],
                "position": position,
                "title": conversation["title"],
                "updated_at_iso": conversation["updated_at"],
                "payload": deepcopy(conversation),
            }

        self._replace_ordered_rows(session, WorkspaceConversation, conversations, make_row)

    def save_state(self, state: WorkspaceState) -> WorkspaceState:
        snapshot = deepcopy(state)
        with self.session_factory.begin() as session:
            self._replace_blob_payloads(session, snapshot)
            self._replace_session_templates(session, snapshot["sessions"])
            self._replace_issued_session_tokens(session, snapshot["issued_session_tokens"])
            self._replace_pending_sso_states(session, snapshot["pending_sso_states"])
            self._replace_admin_users(session, snapshot["admin_users"])
            self._replace_role_policies(session, snapshot["role_policies"])
            self._replace_submissions(session, snapshot["submissions"])
            self._replace_reviews(session, snapshot["reviews"])
            self._replace_system_settings(session, snapshot["system_settings"])
            self._replace_jobs(session, snapshot["jobs"])
            self._replace_audit_logs(session, snapshot["audit_logs"])
            self._replace_dense_audit_logs(session, snapshot["dense_audit_logs"])
            self._replace_documents(session, snapshot["documents"])
            self._replace_conversations(session, snapshot["conversations"])
        return snapshot

    def upsert_pending_sso_state(self, state: str, payload: dict) -> dict:
        with self.session_factory.begin() as session:
            row = session.get(WorkspacePendingSsoState, state)
            values = {
                "state": state,
                "scenario": payload.get("scenario", "happy"),
                "return_to": payload.get("return_to", ""),
                "created_at_iso": payload.get("created_at", ""),
                "payload": deepcopy(payload),
            }
            if row is None:
                session.add(WorkspacePendingSsoState(**values))
            else:
                row.scenario = values["scenario"]
                row.return_to = values["return_to"]
                row.created_at_iso = values["created_at_iso"]
                row.payload = values["payload"]
        return deepcopy(payload)

    def consume_pending_sso_state(self, state: str) -> dict | None:
        with self.session_factory.begin() as session:
            row = session.get(WorkspacePendingSsoState, state)
            if row is None:
                return None
            payload = deepcopy(row.payload)
            session.delete(row)
        return payload

    def update_system_setting_value(self, key: str, value: str) -> dict | None:
        with self.session_factory.begin() as session:
            row = session.get(WorkspaceSystemSetting, key)
            if row is None:
                return None
            payload = deepcopy(row.payload)
            payload["value"] = value
            row.value = value
            row.payload = payload
        return payload

    def upsert_conversation(self, conversation: dict) -> dict:
        with self.session_factory.begin() as session:
            row = session.get(WorkspaceConversation, conversation["id"])
            values = {
                "id": conversation["id"],
                "title": conversation["title"],
                "updated_at_iso": conversation["updated_at"],
                "payload": deepcopy(conversation),
            }
            if row is None:
                next_position = session.scalar(select(func.count()).select_from(WorkspaceConversation)) or 0
                session.add(WorkspaceConversation(position=next_position, **values))
            else:
                row.title = values["title"]
                row.updated_at_iso = values["updated_at_iso"]
                row.payload = values["payload"]
        return deepcopy(conversation)

    def reset(self) -> WorkspaceState:
        seed = build_seed_state()
        with self.session_factory.begin() as session:
            session.execute(delete(WorkspaceStateEntry))
            session.execute(delete(WorkspaceSessionTemplate))
            session.execute(delete(WorkspaceIssuedSessionToken))
            session.execute(delete(WorkspacePendingSsoState))
            session.execute(delete(WorkspaceAdminUser))
            session.execute(delete(WorkspaceRolePolicy))
            session.execute(delete(WorkspaceSubmission))
            session.execute(delete(WorkspaceReview))
            session.execute(delete(WorkspaceSystemSetting))
            session.execute(delete(WorkspaceJob))
            session.execute(delete(WorkspaceAuditLog))
            session.execute(delete(WorkspaceDenseAuditLog))
            session.execute(delete(WorkspaceDocument))
            session.execute(delete(WorkspaceConversation))
        return self.save_state(seed)

    def dispose(self) -> None:
        self.engine.dispose()

    # ── Per-entity CRUD implementations (repository pattern) ──

    def _next_position(self, session: Session, model) -> int:
        """Return a position value that sorts before all existing rows (prepend)."""
        min_pos = session.scalar(select(func.min(model.position)))
        return (min_pos - 1) if min_pos is not None else 0

    # ── Session templates ──

    def get_session_templates(self) -> dict[str, dict]:
        with self.session_factory() as session:
            rows = session.scalars(select(WorkspaceSessionTemplate).order_by(WorkspaceSessionTemplate.role.asc())).all()
            if rows:
                return {row.role: deepcopy(row.payload) for row in rows}
            seed = build_seed_state()
            return deepcopy(seed["sessions"])

    # ── Issued session tokens ──

    def get_issued_session_token(self, token: str) -> dict | None:
        with self.session_factory() as session:
            row = session.get(WorkspaceIssuedSessionToken, token)
            if row is None:
                return None
            payload: dict[str, object] = {"role": row.role}
            if row.auth_method is not None:
                payload["auth_method"] = row.auth_method
            if row.session_payload is not None:
                payload["session"] = deepcopy(row.session_payload)
            return payload

    def create_issued_session_token(self, token: str, payload: dict) -> None:
        with self.session_factory.begin() as session:
            if isinstance(payload, str):
                role = payload
                auth_method = None
                session_payload = None
            else:
                role = payload.get("role", "guest")
                auth_method = payload.get("auth_method")
                session_payload = deepcopy(payload.get("session"))
            row = session.get(WorkspaceIssuedSessionToken, token)
            values = {
                "token": token,
                "role": role,
                "auth_method": auth_method,
                "session_payload": session_payload,
            }
            if row is None:
                session.add(WorkspaceIssuedSessionToken(**values))
            else:
                row.role = values["role"]
                row.auth_method = values["auth_method"]
                row.session_payload = values["session_payload"]

    def delete_issued_session_token(self, token: str) -> None:
        with self.session_factory.begin() as session:
            row = session.get(WorkspaceIssuedSessionToken, token)
            if row is not None:
                session.delete(row)

    # ── Pending SSO states ──

    def get_pending_sso_states(self) -> dict[str, dict]:
        with self.session_factory() as session:
            rows = session.scalars(select(WorkspacePendingSsoState)).all()
            return {row.state: deepcopy(row.payload) for row in rows}

    # ── Documents ──

    def get_document_by_id(self, doc_id: str) -> dict | None:
        with self.session_factory() as session:
            row = session.get(WorkspaceDocument, doc_id)
            return deepcopy(row.payload) if row else None

    def list_all_documents(self) -> list[dict]:
        with self.session_factory() as session:
            rows = session.scalars(select(WorkspaceDocument).order_by(WorkspaceDocument.position.asc())).all()
            return [deepcopy(row.payload) for row in rows]

    def create_document(self, doc: dict) -> dict:
        with self.session_factory.begin() as session:
            system_metadata = doc["system_metadata"]
            supplemental_metadata = doc["supplemental_metadata"]
            position = self._next_position(session, WorkspaceDocument)
            session.add(WorkspaceDocument(
                id=doc["id"],
                position=position,
                title=doc["title"],
                owner_email=doc["owner_email"],
                lifecycle_status=doc["lifecycle_status"],
                processing_status=doc["processing_status"],
                visibility_scope=supplemental_metadata["visibility_scope"],
                is_archived=bool(system_metadata["is_archived"]),
                created_at_iso=doc["created_at"],
                updated_at_iso=doc["updated_at"],
                indexed_at_iso=system_metadata.get("indexed_at"),
                payload=deepcopy(doc),
            ))
        return deepcopy(doc)

    def update_document_payload(self, doc_id: str, doc: dict) -> dict:
        with self.session_factory.begin() as session:
            row = session.get(WorkspaceDocument, doc_id)
            if row is None:
                raise ValueError(f"Document {doc_id} not found")
            system_metadata = doc["system_metadata"]
            supplemental_metadata = doc["supplemental_metadata"]
            row.title = doc["title"]
            row.owner_email = doc["owner_email"]
            row.lifecycle_status = doc["lifecycle_status"]
            row.processing_status = doc["processing_status"]
            row.visibility_scope = supplemental_metadata["visibility_scope"]
            row.is_archived = bool(system_metadata["is_archived"])
            row.created_at_iso = doc["created_at"]
            row.updated_at_iso = doc["updated_at"]
            row.indexed_at_iso = system_metadata.get("indexed_at")
            row.payload = deepcopy(doc)
        return deepcopy(doc)

    # ── Submissions ──

    def get_submission_by_id(self, sub_id: str) -> dict | None:
        with self.session_factory() as session:
            row = session.get(WorkspaceSubmission, sub_id)
            return deepcopy(row.payload) if row else None

    def list_all_submissions(self) -> list[dict]:
        with self.session_factory() as session:
            rows = session.scalars(select(WorkspaceSubmission).order_by(WorkspaceSubmission.position.asc())).all()
            return [deepcopy(row.payload) for row in rows]

    def create_submission(self, sub: dict) -> dict:
        with self.session_factory.begin() as session:
            position = self._next_position(session, WorkspaceSubmission)
            session.add(WorkspaceSubmission(
                id=sub["id"],
                position=position,
                title=sub["title"],
                source_type=sub["source_type"],
                lifecycle_status=sub["lifecycle_status"],
                processing_status=sub["processing_status"],
                linked_document_id=sub.get("linked_document_id"),
                visibility_scope=sub["supplemental_metadata"]["visibility_scope"],
                created_at_iso=sub["created_at"],
                updated_at_iso=sub["updated_at"],
                payload=deepcopy(sub),
            ))
        return deepcopy(sub)

    def update_submission_payload(self, sub_id: str, sub: dict) -> dict:
        with self.session_factory.begin() as session:
            row = session.get(WorkspaceSubmission, sub_id)
            if row is None:
                raise ValueError(f"Submission {sub_id} not found")
            row.title = sub["title"]
            row.lifecycle_status = sub["lifecycle_status"]
            row.processing_status = sub["processing_status"]
            row.linked_document_id = sub.get("linked_document_id")
            row.visibility_scope = sub["supplemental_metadata"]["visibility_scope"]
            row.updated_at_iso = sub["updated_at"]
            row.payload = deepcopy(sub)
        return deepcopy(sub)

    # ── Reviews ──

    def get_review_by_id(self, review_id: str) -> dict | None:
        with self.session_factory() as session:
            row = session.get(WorkspaceReview, review_id)
            return deepcopy(row.payload) if row else None

    def list_all_reviews(self) -> list[dict]:
        with self.session_factory() as session:
            rows = session.scalars(select(WorkspaceReview).order_by(WorkspaceReview.position.asc())).all()
            return [deepcopy(row.payload) for row in rows]

    def create_review(self, review: dict) -> dict:
        with self.session_factory.begin() as session:
            position = self._next_position(session, WorkspaceReview)
            session.add(WorkspaceReview(
                id=review["id"],
                position=position,
                submission_id=review["submission_id"],
                published_document_id=review.get("published_document_id"),
                title=review["title"],
                source_type=review["source_type"],
                visibility_scope=review["visibility_scope"],
                status=review["status"],
                confidence=float(review["confidence"]),
                reviewer_name=review["reviewer_name"],
                created_at_iso=review["created_at"],
                payload=deepcopy(review),
            ))
        return deepcopy(review)

    def update_review_payload(self, review_id: str, review: dict) -> dict:
        with self.session_factory.begin() as session:
            row = session.get(WorkspaceReview, review_id)
            if row is None:
                raise ValueError(f"Review {review_id} not found")
            row.submission_id = review["submission_id"]
            row.published_document_id = review.get("published_document_id")
            row.title = review["title"]
            row.source_type = review["source_type"]
            row.visibility_scope = review["visibility_scope"]
            row.status = review["status"]
            row.confidence = float(review["confidence"])
            row.reviewer_name = review["reviewer_name"]
            row.payload = deepcopy(review)
        return deepcopy(review)

    # ── Jobs ──

    def get_job_by_id(self, job_id: str) -> dict | None:
        with self.session_factory() as session:
            row = session.get(WorkspaceJob, job_id)
            return deepcopy(row.payload) if row else None

    def list_all_jobs(self) -> list[dict]:
        with self.session_factory() as session:
            rows = session.scalars(select(WorkspaceJob).order_by(WorkspaceJob.position.asc())).all()
            return [deepcopy(row.payload) for row in rows]

    def create_job(self, job: dict) -> dict:
        with self.session_factory.begin() as session:
            position = self._next_position(session, WorkspaceJob)
            session.add(WorkspaceJob(
                id=job["id"],
                position=position,
                job_type=job["type"],
                status=job["status"],
                progress=float(job["progress"]),
                related_title=job["related_title"],
                started_at_iso=job["started_at"],
                updated_at_iso=job["updated_at"],
                payload=deepcopy(job),
            ))
        return deepcopy(job)

    def update_job_payload(self, job_id: str, job: dict) -> dict:
        with self.session_factory.begin() as session:
            row = session.get(WorkspaceJob, job_id)
            if row is None:
                raise ValueError(f"Job {job_id} not found")
            row.job_type = job["type"]
            row.status = job["status"]
            row.progress = float(job["progress"])
            row.related_title = job["related_title"]
            row.updated_at_iso = job["updated_at"]
            row.payload = deepcopy(job)
        return deepcopy(job)

    # ── Admin users ──

    def get_admin_user_by_id(self, user_id: str) -> dict | None:
        with self.session_factory() as session:
            row = session.get(WorkspaceAdminUser, user_id)
            return deepcopy(row.payload) if row else None

    def get_admin_user_by_email(self, email: str) -> dict | None:
        with self.session_factory() as session:
            row = session.scalar(
                select(WorkspaceAdminUser).where(
                    func.lower(WorkspaceAdminUser.email) == email.strip().lower()
                )
            )
            return deepcopy(row.payload) if row else None

    def list_all_admin_users(self) -> list[dict]:
        with self.session_factory() as session:
            rows = session.scalars(select(WorkspaceAdminUser).order_by(WorkspaceAdminUser.position.asc())).all()
            return [deepcopy(row.payload) for row in rows]

    def upsert_admin_user(self, user: dict) -> dict:
        with self.session_factory.begin() as session:
            row = session.get(WorkspaceAdminUser, user["id"])
            values = {
                "id": user["id"],
                "email": user["email"],
                "role": user["role"],
                "status": user["status"],
                "scope": user["scope"],
                "last_active_at_iso": user["last_active_at"],
                "is_internal_domain_compliant": bool(user["is_internal_domain_compliant"]),
                "payload": deepcopy(user),
            }
            if row is None:
                position = self._next_position(session, WorkspaceAdminUser)
                session.add(WorkspaceAdminUser(position=position, **values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
        return deepcopy(user)

    def update_admin_user_payload(self, user_id: str, user: dict) -> dict:
        with self.session_factory.begin() as session:
            row = session.get(WorkspaceAdminUser, user_id)
            if row is None:
                raise ValueError(f"Admin user {user_id} not found")
            row.email = user["email"]
            row.role = user["role"]
            row.status = user["status"]
            row.scope = user["scope"]
            row.last_active_at_iso = user["last_active_at"]
            row.is_internal_domain_compliant = bool(user["is_internal_domain_compliant"])
            row.payload = deepcopy(user)
        return deepcopy(user)

    # ── Role policies ──

    def list_all_role_policies(self) -> list[dict]:
        with self.session_factory() as session:
            rows = session.scalars(select(WorkspaceRolePolicy).order_by(WorkspaceRolePolicy.position.asc())).all()
            return [deepcopy(row.payload) for row in rows]

    # ── System settings ──

    def list_all_system_settings(self) -> list[dict]:
        with self.session_factory() as session:
            rows = session.scalars(select(WorkspaceSystemSetting).order_by(WorkspaceSystemSetting.position.asc())).all()
            return [deepcopy(row.payload) for row in rows]

    # ── Audit logs ──

    def list_all_audit_logs(self) -> list[dict]:
        with self.session_factory() as session:
            rows = session.scalars(select(WorkspaceAuditLog).order_by(WorkspaceAuditLog.position.asc())).all()
            return [deepcopy(row.payload) for row in rows]

    def create_audit_log(self, entry: dict) -> dict:
        with self.session_factory.begin() as session:
            position = self._next_position(session, WorkspaceAuditLog)
            session.add(WorkspaceAuditLog(
                id=entry["id"],
                position=position,
                actor_name=entry["actor_name"],
                actor_role=entry["actor_role"],
                action=entry["action"],
                target_type=entry["target_type"],
                target_id=entry["target_id"],
                target_label=entry["target_label"],
                created_at_iso=entry["created_at"],
                payload=deepcopy(entry),
            ))
        return deepcopy(entry)

    def list_all_dense_audit_logs(self) -> list[dict]:
        with self.session_factory() as session:
            rows = session.scalars(select(WorkspaceDenseAuditLog).order_by(WorkspaceDenseAuditLog.position.asc())).all()
            return [deepcopy(row.payload) for row in rows]

    # ── Conversations ──

    def list_all_conversations(self) -> list[dict]:
        with self.session_factory() as session:
            rows = session.scalars(select(WorkspaceConversation).order_by(WorkspaceConversation.position.asc())).all()
            return [deepcopy(row.payload) for row in rows]

    def get_conversation_by_id(self, conv_id: str) -> dict | None:
        with self.session_factory() as session:
            row = session.get(WorkspaceConversation, conv_id)
            return deepcopy(row.payload) if row else None
