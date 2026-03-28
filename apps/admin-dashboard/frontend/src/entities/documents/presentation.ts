import type { Document, DocumentLifecycleStatus, ProcessingStatus, VisibilityScope } from '@/entities/documents/types'

export function formatStatusLabel(value: string) {
    return value.replace(/_/g, ' ')
}

export function getLifecycleTone(status: DocumentLifecycleStatus) {
    switch (status) {
        case 'approved':
            return 'success' as const
        case 'pending_review':
            return 'warning' as const
        case 'rejected':
            return 'danger' as const
        case 'archived':
            return 'danger' as const
        default:
            return 'neutral' as const
    }
}

export function getProcessingTone(status: ProcessingStatus) {
    switch (status) {
        case 'completed':
            return 'success' as const
        case 'failed':
            return 'danger' as const
        case 'extracting':
        case 'indexing':
        case 'uploading':
            return 'brand' as const
        default:
            return 'neutral' as const
    }
}

export function getVisibilityTone(scope: VisibilityScope) {
    return scope === 'public' ? ('brand' as const) : ('neutral' as const)
}

export function getDocumentTrustState(document: Document) {
    if (document.system.isArchived || document.lifecycleStatus === 'archived') {
        return {
            tone: 'danger' as const,
            title: 'Archived source',
            description: 'This document is kept for historical reference and should not be treated as current policy.',
        }
    }

    if (document.lifecycleStatus === 'pending_review') {
        return {
            tone: 'warning' as const,
            title: 'Pending reviewer approval',
            description: 'This document is visible for internal validation only and should not be treated as trusted public guidance.',
        }
    }

    if (document.lifecycleStatus === 'rejected') {
        return {
            tone: 'danger' as const,
            title: 'Rejected source',
            description: 'The review process rejected this source, so it should not feed student-facing answers.',
        }
    }

    if (document.supplemental.visibilityScope === 'internal') {
        return {
            tone: 'brand' as const,
            title: 'Trusted internal source',
            description: 'The document is approved but remains restricted to internal staff and operators.',
        }
    }

    return {
        tone: 'success' as const,
        title: 'Public-ready source',
        description: 'The document is approved and eligible to be cited in the student-facing assistant.',
    }
}
