import { mapTemporalMetadata } from '@/entities/documents/mappers'
import type { ReviewTask, ReviewTaskDto } from '@/entities/reviews/types'

export function mapReviewTaskDtoToReviewTask(dto: ReviewTaskDto): ReviewTask {
    return {
        id: dto.id,
        submissionId: dto.submission_id,
        publishedDocumentId: dto.published_document_id,
        title: dto.title,
        sourceType: dto.source_type,
        visibilityScope: dto.visibility_scope,
        submittedByName: dto.submitted_by_name,
        submittedByEmail: dto.submitted_by_email,
        reviewerName: dto.reviewer_name,
        status: dto.status,
        confidence: dto.confidence,
        createdAt: dto.created_at,
        extractedTemporal: mapTemporalMetadata(dto.extracted_temporal_metadata),
        editedTemporal: mapTemporalMetadata(dto.edited_temporal_metadata),
        reason: dto.reason,
    }
}
