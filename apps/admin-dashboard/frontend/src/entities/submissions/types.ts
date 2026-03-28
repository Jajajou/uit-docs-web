import type {
    DocumentLifecycleStatus,
    DocumentSystemMetadata,
    DocumentSystemMetadataDto,
    DocumentSupplementalMetadata,
    DocumentSupplementalMetadataDto,
    DocumentTemporalMetadata,
    DocumentTemporalMetadataDto,
    ProcessingStatus,
} from '@/entities/documents/types'

export type UploadSourceType = 'file' | 'text' | 'url'

export interface SubmissionTraceability {
    reviewTaskId: string | null
    publishedDocumentId: string | null
    reviewedByName: string | null
    publishedAt: string | null
    publicationReason: string | null
}

export interface Submission {
    id: string
    title: string
    sourceType: UploadSourceType
    lifecycleStatus: DocumentLifecycleStatus
    processingStatus: ProcessingStatus
    createdAt: string
    updatedAt: string
    linkedDocumentId: string | null
    temporal: DocumentTemporalMetadata
    system: DocumentSystemMetadata
    supplemental: DocumentSupplementalMetadata
    traceability: SubmissionTraceability | null
}

export interface SubmissionDto {
    id: string
    title: string
    source_type: UploadSourceType
    lifecycle_status: DocumentLifecycleStatus
    processing_status: ProcessingStatus
    created_at: string
    updated_at: string
    linked_document_id: string | null
    temporal_metadata: DocumentTemporalMetadataDto
    system_metadata: DocumentSystemMetadataDto
    supplemental_metadata: DocumentSupplementalMetadataDto
    traceability?: {
        review_task_id?: string | null
        published_document_id?: string | null
        reviewed_by_name?: string | null
        published_at?: string | null
        publication_reason?: string | null
    } | null
}

export interface UploadMutationPayload {
    sourceType: UploadSourceType
    title: string
    content?: string
    url?: string
    fileName?: string
    issuingUnit: string
    visibilityScope: 'public' | 'internal'
    tags: string[]
    notes: string
}
