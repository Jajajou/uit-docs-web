"""Pydantic schemas aligned with the /web frontend contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["guest", "student", "teacher", "admin"]
DocumentLifecycleStatus = Literal["draft", "pending_review", "approved", "rejected", "archived"]
ProcessingStatus = Literal["pending", "uploading", "extracting", "indexing", "completed", "failed"]
VisibilityScope = Literal["public", "internal"]
UploadSourceType = Literal["file", "text", "url"]
AdminShellScope = Literal["public", "app", "auth", "admin", "system"]
AdminUserStatus = Literal["active", "invited", "suspended"]
AdminUserScope = Literal["student_portal", "teacher_workspace", "admin_console"]
SystemSettingGroup = Literal["auth", "ingestion", "publication", "chat"]
SystemSettingSource = Literal["derived_contract", "mock_policy"]
AuditActionType = Literal[
    "upload_submission",
    "approve_review",
    "reject_review",
    "request_changes",
    "archive_document",
    "reindex_document",
    "login",
    "role_switch",
]
AuditTargetType = Literal["submission", "review", "document", "session"]
JobType = Literal["upload", "indexing", "scan"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApiErrorPayload(StrictModel):
    code: str
    message: str
    status: int
    requestId: str | None = None
    details: Any = None


class ErrorResponse(StrictModel):
    error: ApiErrorPayload


class UserDto(StrictModel):
    id: str
    name: str
    email: str
    role: Role
    department: str
    avatar_initials: str


class SessionDto(StrictModel):
    session_id: str
    status: Literal["anonymous", "authenticated"]
    user: UserDto


class AuthBootstrapRequest(StrictModel):
    role: Role


class SsoProviderMetadataDto(StrictModel):
    mode: Literal["emulator", "external"]
    provider_name: str
    uses_local_emulator: bool
    configured: bool
    authorization_endpoint: str | None = None
    callback_path: str
    role_claim: str
    group_claim: str
    email_claim: str
    default_scope: str


class AnswerReferenceDto(StrictModel):
    id: str
    title: str
    href: str
    excerpt: str
    status_label: str


class AnswerWarningDto(StrictModel):
    code: str
    message: str


class MessageDto(StrictModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: str
    confidence: float | None = None
    references: list[AnswerReferenceDto]
    warnings: list[AnswerWarningDto]


class ConversationDto(StrictModel):
    id: str
    title: str
    updated_at: str
    messages: list[MessageDto]


class ChatResponseDto(StrictModel):
    conversation_id: str
    message: MessageDto


class ConversationsResponse(StrictModel):
    conversations: list[ConversationDto]


class ChatStreamRequest(StrictModel):
    conversationId: str | None = None
    message: str


class ChatLiveSyncRequest(StrictModel):
    conversationId: str | None = None
    message: str
    result: dict[str, Any]


class DocumentTemporalMetadataDto(StrictModel):
    document_type: str
    extraction_method: str
    temporal_confidence: float
    temporal_reasoning: str
    valid_from: str | None = None
    valid_until: str | None = None
    academic_year: str | None = None
    cohort_years: list[str] = Field(default_factory=list)
    document_number: str | None = None
    amends_documents: list[str] = Field(default_factory=list)


class DocumentSystemMetadataDto(StrictModel):
    file_source: str
    indexed_at: str
    content_hash: str
    is_archived: bool
    version_number: int


class DocumentSupplementalMetadataDto(StrictModel):
    title: str
    issuing_unit: str
    tags: list[str]
    visibility_scope: VisibilityScope
    notes: str


class DocumentVersionEntryDto(StrictModel):
    id: str
    version_number: int
    created_at: str
    created_by_name: str
    change_summary: str
    file_source: str
    content_hash: str
    is_current: bool
    source_submission_id: str | None = None
    source_review_id: str | None = None
    change_highlights: list[str] = Field(default_factory=list)


class DocumentTraceabilityDto(StrictModel):
    source_submission_id: str | None = None
    source_review_id: str | None = None
    reviewed_by_name: str | None = None
    published_at: str | None = None
    publication_reason: str | None = None


class DocumentActivityEntryDto(StrictModel):
    id: str
    actor_name: str
    actor_role: Role
    action: AuditActionType
    target_type: AuditTargetType
    target_id: str
    target_label: str
    created_at: str


class DocumentDto(StrictModel):
    id: str
    title: str
    owner_name: str
    owner_email: str
    lifecycle_status: DocumentLifecycleStatus
    processing_status: ProcessingStatus
    created_at: str
    updated_at: str
    temporal_metadata: DocumentTemporalMetadataDto
    system_metadata: DocumentSystemMetadataDto
    supplemental_metadata: DocumentSupplementalMetadataDto
    traceability: DocumentTraceabilityDto | None = None
    version_history: list[DocumentVersionEntryDto] = Field(default_factory=list)
    activity_history: list[DocumentActivityEntryDto] = Field(default_factory=list)


class DocumentsResponse(StrictModel):
    documents: list[DocumentDto]


class DocumentResponse(StrictModel):
    document: DocumentDto


class SubmissionTraceabilityDto(StrictModel):
    review_task_id: str | None = None
    published_document_id: str | None = None
    reviewed_by_name: str | None = None
    published_at: str | None = None
    publication_reason: str | None = None


class SubmissionDto(StrictModel):
    id: str
    title: str
    source_type: UploadSourceType
    lifecycle_status: DocumentLifecycleStatus
    processing_status: ProcessingStatus
    created_at: str
    updated_at: str
    linked_document_id: str | None
    temporal_metadata: DocumentTemporalMetadataDto
    system_metadata: DocumentSystemMetadataDto
    supplemental_metadata: DocumentSupplementalMetadataDto
    traceability: SubmissionTraceabilityDto | None = None


class SubmissionsResponse(StrictModel):
    submissions: list[SubmissionDto]


class SubmissionResponse(StrictModel):
    submission: SubmissionDto


class UploadSubmissionRequest(StrictModel):
    sourceType: UploadSourceType
    title: str
    content: str | None = None
    url: str | None = None
    fileName: str | None = None
    issuingUnit: str | None = None
    visibilityScope: VisibilityScope | None = None
    tags: list[str] | None = None
    notes: str | None = None


class ReviewTaskDto(StrictModel):
    id: str
    submission_id: str
    published_document_id: str | None
    title: str
    source_type: UploadSourceType
    visibility_scope: VisibilityScope
    submitted_by_name: str
    submitted_by_email: str
    reviewer_name: str
    status: Literal["pending_review", "approved", "rejected"]
    confidence: float
    created_at: str
    extracted_temporal_metadata: DocumentTemporalMetadataDto
    edited_temporal_metadata: DocumentTemporalMetadataDto
    reason: str


class ReviewsResponse(StrictModel):
    tasks: list[ReviewTaskDto]


class ReviewTaskResponse(StrictModel):
    task: ReviewTaskDto


class ReviewDecisionRequest(StrictModel):
    status: Literal["pending_review", "approved", "rejected"]
    reason: str | None = None
    edited_temporal_metadata: DocumentTemporalMetadataDto | None = None


class JobDto(StrictModel):
    id: str
    type: JobType
    status: ProcessingStatus
    progress: int
    related_title: str
    started_at: str
    updated_at: str
    message: str


class JobsResponse(StrictModel):
    jobs: list[JobDto]


class RetryJobResponse(StrictModel):
    job: JobDto
    retry_accepted: bool


class AdminUserDto(StrictModel):
    id: str
    name: str
    email: str
    role: Role
    status: AdminUserStatus
    scope: AdminUserScope
    last_active_at: str
    is_internal_domain_compliant: bool


class RolePolicyDto(StrictModel):
    role: Role
    allowed_shells: list[AdminShellScope]
    allowed_routes: list[str]
    requires_internal_email: bool


class SystemSettingDto(StrictModel):
    group: SystemSettingGroup
    key: str
    label: str
    value: str
    description: str
    is_sensitive: bool
    source: SystemSettingSource


class AuditLogEntryDto(StrictModel):
    id: str
    actor_name: str
    actor_role: Role
    action: AuditActionType
    target_type: AuditTargetType
    target_id: str
    target_label: str
    created_at: str


class AdminUsersResponse(StrictModel):
    users: list[AdminUserDto]


class RolePoliciesResponse(StrictModel):
    roles: list[RolePolicyDto]


class SystemSettingsResponse(StrictModel):
    settings: list[SystemSettingDto]


class AuditLogsResponse(StrictModel):
    logs: list[AuditLogEntryDto]


class AdminUserPatchRequest(StrictModel):
    role: Role | None = None
    status: AdminUserStatus | None = None
    scope: AdminUserScope | None = None


class AdminUserResponse(StrictModel):
    user: AdminUserDto


class SystemSettingPatchRequest(StrictModel):
    value: str


class SystemSettingResponse(StrictModel):
    setting: SystemSettingDto


class OverviewStats(StrictModel):
    total_documents: int
    indexed: int
    processing: int
    failed: int
    pending: int
    lightrag_health: str


class PipelineStatus(StrictModel):
    is_processing: bool
    queue_size: int
    last_processed: str | None = None
    error_message: str | None = None


class GraphStatsResponse(StrictModel):
    total_labels: int
    top_labels: list[str]


class HealthResponse(StrictModel):
    admin_api: str
    lightrag: str
    lightrag_url: str
