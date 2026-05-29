import { mapSupplementalMetadata, mapSystemMetadata, mapTemporalMetadata } from '@/entities/documents/mappers'
import type { Submission, SubmissionDto } from '@/entities/submissions/types'

export function mapSubmissionDtoToSubmission(dto: SubmissionDto): Submission {
    return {
        id: dto.id,
        title: dto.title,
        sourceType: dto.source_type,
        lifecycleStatus: dto.lifecycle_status,
        processingStatus: dto.processing_status,
        createdAt: dto.created_at,
        updatedAt: dto.updated_at,
        linkedDocumentId: dto.linked_document_id,
        temporal: mapTemporalMetadata(dto.temporal_metadata),
        system: mapSystemMetadata(dto.system_metadata),
        supplemental: mapSupplementalMetadata(dto.supplemental_metadata),
        traceability: dto.traceability
            ? {
                reviewTaskId: dto.traceability.review_task_id ?? null,
                publishedDocumentId: dto.traceability.published_document_id ?? null,
                reviewedByName: dto.traceability.reviewed_by_name ?? null,
                publishedAt: dto.traceability.published_at ?? null,
                publicationReason: dto.traceability.publication_reason ?? null,
            }
            : null,
    }
}
