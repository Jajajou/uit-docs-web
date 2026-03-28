import type { AuditActionType, AuditTargetType } from '@/entities/admin/types'
import type { Role } from '@/entities/auth/types'

export type DocumentLifecycleStatus = 'draft' | 'pending_review' | 'approved' | 'rejected' | 'archived'
export type ProcessingStatus = 'pending' | 'uploading' | 'extracting' | 'indexing' | 'completed' | 'failed'
export type VisibilityScope = 'public' | 'internal'

export interface DocumentTemporalMetadata {
    documentType: string
    extractionMethod: string
    confidence: number
    reasoning: string
    validFrom: string | null
    validUntil: string | null
    academicYear: string | null
    cohortYears: string[]
    documentNumber: string | null
    amendsDocuments: string[]
}

export interface DocumentSystemMetadata {
    fileSource: string
    indexedAt: string
    contentHash: string
    isArchived: boolean
    versionNumber: number
}

export interface DocumentSupplementalMetadata {
    title: string
    issuingUnit: string
    tags: string[]
    visibilityScope: VisibilityScope
    notes: string
}

export interface DocumentVersionEntry {
    id: string
    versionNumber: number
    createdAt: string
    createdByName: string
    changeSummary: string
    fileSource: string
    contentHash: string
    isCurrent: boolean
    sourceSubmissionId: string | null
    sourceReviewId: string | null
    changeHighlights: string[]
}

export interface DocumentActivityEntry {
    id: string
    actorName: string
    actorRole: Role
    action: AuditActionType
    targetType: AuditTargetType
    targetId: string
    targetLabel: string
    createdAt: string
}

export interface DocumentTraceability {
    sourceSubmissionId: string | null
    sourceReviewId: string | null
    reviewedByName: string | null
    publishedAt: string | null
    publicationReason: string | null
}

export interface Document {
    id: string
    title: string
    ownerName: string
    ownerEmail: string
    lifecycleStatus: DocumentLifecycleStatus
    processingStatus: ProcessingStatus
    createdAt: string
    updatedAt: string
    temporal: DocumentTemporalMetadata
    system: DocumentSystemMetadata
    supplemental: DocumentSupplementalMetadata
    traceability: DocumentTraceability | null
    versionHistory: DocumentVersionEntry[]
    activityHistory: DocumentActivityEntry[]
}

export interface DocumentTemporalMetadataDto {
    document_type: string
    extraction_method: string
    temporal_confidence: number
    temporal_reasoning: string
    valid_from: string | null
    valid_until: string | null
    academic_year: string | null
    cohort_years: string[] | null
    document_number: string | null
    amends_documents: string[]
}

export interface DocumentSystemMetadataDto {
    file_source: string
    indexed_at: string
    content_hash: string
    is_archived: boolean
    version_number: number
}

export interface DocumentSupplementalMetadataDto {
    title: string
    issuing_unit: string
    tags: string[]
    visibility_scope: VisibilityScope
    notes: string
}

export interface DocumentVersionEntryDto {
    id: string
    version_number: number
    created_at: string
    created_by_name: string
    change_summary: string
    file_source: string
    content_hash: string
    is_current: boolean
    source_submission_id?: string | null
    source_review_id?: string | null
    change_highlights?: string[]
}

export interface DocumentTraceabilityDto {
    source_submission_id?: string | null
    source_review_id?: string | null
    reviewed_by_name?: string | null
    published_at?: string | null
    publication_reason?: string | null
}

export interface DocumentActivityEntryDto {
    id: string
    actor_name: string
    actor_role: Role
    action: AuditActionType
    target_type: AuditTargetType
    target_id: string
    target_label: string
    created_at: string
}

export interface DocumentDto {
    id: string
    title: string
    owner_name: string
    owner_email: string
    lifecycle_status: DocumentLifecycleStatus
    processing_status: ProcessingStatus
    created_at: string
    updated_at: string
    temporal_metadata: DocumentTemporalMetadataDto
    system_metadata: DocumentSystemMetadataDto
    supplemental_metadata: DocumentSupplementalMetadataDto
    traceability?: DocumentTraceabilityDto | null
    version_history?: DocumentVersionEntryDto[]
    activity_history?: DocumentActivityEntryDto[]
}
