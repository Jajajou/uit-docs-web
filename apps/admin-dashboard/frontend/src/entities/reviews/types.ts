import type {
    DocumentLifecycleStatus,
    VisibilityScope,
    DocumentTemporalMetadata,
    DocumentTemporalMetadataDto,
} from '@/entities/documents/types'
import type { UploadSourceType } from '@/entities/submissions/types'

export interface ReviewTask {
    id: string
    submissionId: string
    publishedDocumentId: string | null
    title: string
    sourceType: UploadSourceType
    visibilityScope: VisibilityScope
    submittedByName: string
    submittedByEmail: string
    reviewerName: string
    status: Extract<DocumentLifecycleStatus, 'pending_review' | 'approved' | 'rejected'>
    confidence: number
    createdAt: string
    extractedTemporal: DocumentTemporalMetadata
    editedTemporal: DocumentTemporalMetadata
    reason: string
}

export interface ReviewTaskDto {
    id: string
    submission_id: string
    published_document_id: string | null
    title: string
    source_type: UploadSourceType
    visibility_scope: VisibilityScope
    submitted_by_name: string
    submitted_by_email: string
    reviewer_name: string
    status: Extract<DocumentLifecycleStatus, 'pending_review' | 'approved' | 'rejected'>
    confidence: number
    created_at: string
    extracted_temporal_metadata: DocumentTemporalMetadataDto
    edited_temporal_metadata: DocumentTemporalMetadataDto
    reason: string
}

export interface ReviewDecisionMutationPayload {
    status: Extract<DocumentLifecycleStatus, 'pending_review' | 'approved' | 'rejected'>
    reason?: string
    editedTemporalMetadata?: DocumentTemporalMetadataDto
}
