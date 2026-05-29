import type {
    DocumentActivityEntry,
    DocumentActivityEntryDto,
    Document,
    DocumentDto,
    DocumentSupplementalMetadata,
    DocumentSystemMetadata,
    DocumentTemporalMetadata,
    DocumentTemporalMetadataDto,
    DocumentTraceability,
    DocumentVersionEntry,
    DocumentVersionEntryDto,
} from '@/entities/documents/types'
import { normalizeRole } from '@/entities/auth/roles'

export function mapTemporalMetadata(dto: DocumentDto['temporal_metadata']): DocumentTemporalMetadata {
    return {
        documentType: dto.document_type,
        extractionMethod: dto.extraction_method,
        confidence: dto.temporal_confidence,
        reasoning: dto.temporal_reasoning,
        validFrom: dto.valid_from,
        validUntil: dto.valid_until,
        academicYear: dto.academic_year,
        cohortYears: dto.cohort_years ?? [],
        documentNumber: dto.document_number,
        amendsDocuments: dto.amends_documents,
    }
}

export function mapTemporalMetadataToDto(metadata: DocumentTemporalMetadata): DocumentTemporalMetadataDto {
    return {
        document_type: metadata.documentType,
        extraction_method: metadata.extractionMethod,
        temporal_confidence: metadata.confidence,
        temporal_reasoning: metadata.reasoning,
        valid_from: metadata.validFrom,
        valid_until: metadata.validUntil,
        academic_year: metadata.academicYear,
        cohort_years: metadata.cohortYears,
        document_number: metadata.documentNumber,
        amends_documents: metadata.amendsDocuments,
    }
}

export function mapSystemMetadata(dto: DocumentDto['system_metadata']): DocumentSystemMetadata {
    return {
        fileSource: dto.file_source,
        indexedAt: dto.indexed_at,
        contentHash: dto.content_hash,
        isArchived: dto.is_archived,
        versionNumber: dto.version_number,
    }
}

export function mapSupplementalMetadata(
    dto: DocumentDto['supplemental_metadata'],
): DocumentSupplementalMetadata {
    return {
        title: dto.title,
        issuingUnit: dto.issuing_unit,
        tags: dto.tags,
        visibilityScope: dto.visibility_scope,
        notes: dto.notes,
    }
}

export function mapDocumentVersionEntry(dto: DocumentVersionEntryDto): DocumentVersionEntry {
    return {
        id: dto.id,
        versionNumber: dto.version_number,
        createdAt: dto.created_at,
        createdByName: dto.created_by_name,
        changeSummary: dto.change_summary,
        fileSource: dto.file_source,
        contentHash: dto.content_hash,
        isCurrent: dto.is_current,
        sourceSubmissionId: dto.source_submission_id ?? null,
        sourceReviewId: dto.source_review_id ?? null,
        changeHighlights: dto.change_highlights ?? [],
    }
}

export function mapDocumentTraceability(dto: DocumentDto['traceability']): DocumentTraceability | null {
    if (!dto) {
        return null
    }

    return {
        sourceSubmissionId: dto.source_submission_id ?? null,
        sourceReviewId: dto.source_review_id ?? null,
        reviewedByName: dto.reviewed_by_name ?? null,
        publishedAt: dto.published_at ?? null,
        publicationReason: dto.publication_reason ?? null,
    }
}

export function mapDocumentActivityEntry(dto: DocumentActivityEntryDto): DocumentActivityEntry {
    return {
        id: dto.id,
        actorName: dto.actor_name,
        actorRole: normalizeRole(dto.actor_role),
        action: dto.action,
        targetType: dto.target_type,
        targetId: dto.target_id,
        targetLabel: dto.target_label,
        createdAt: dto.created_at,
    }
}

export function mapDocumentDtoToDocument(dto: DocumentDto): Document {
    return {
        id: dto.id,
        title: dto.title,
        ownerName: dto.owner_name,
        ownerEmail: dto.owner_email,
        lifecycleStatus: dto.lifecycle_status,
        processingStatus: dto.processing_status,
        createdAt: dto.created_at,
        updatedAt: dto.updated_at,
        temporal: mapTemporalMetadata(dto.temporal_metadata),
        system: mapSystemMetadata(dto.system_metadata),
        supplemental: mapSupplementalMetadata(dto.supplemental_metadata),
        traceability: mapDocumentTraceability(dto.traceability),
        versionHistory: (dto.version_history ?? []).map(mapDocumentVersionEntry),
        activityHistory: (dto.activity_history ?? []).map(mapDocumentActivityEntry),
    }
}
