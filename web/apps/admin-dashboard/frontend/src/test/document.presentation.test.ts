import { describe, expect, it } from 'vitest'
import { mapDocumentDtoToDocument } from '@/entities/documents/mappers'
import {
    formatStatusLabel,
    getDocumentTrustState,
    getLifecycleTone,
    getProcessingTone,
    getVisibilityTone,
} from '@/entities/documents/presentation'
import { documentFixtures } from '@/mocks/fixtures/documents'

describe('document presentation helpers', () => {
    it('marks approved public documents as public-ready sources', () => {
        const document = mapDocumentDtoToDocument(documentFixtures[3])

        expect(getDocumentTrustState(document)).toMatchObject({
            tone: 'success',
            title: 'Public-ready source',
        })
    })

    it('marks pending documents as untrusted for public guidance', () => {
        const document = mapDocumentDtoToDocument(documentFixtures[1])

        expect(getDocumentTrustState(document)).toMatchObject({
            tone: 'warning',
            title: 'Pending reviewer approval',
        })
    })

    it('marks archived documents as historical only', () => {
        const document = mapDocumentDtoToDocument(documentFixtures[2])

        expect(getDocumentTrustState(document)).toMatchObject({
            tone: 'danger',
            title: 'Archived source',
        })
    })

    it('marks approved internal documents as trusted internal sources', () => {
        const document = mapDocumentDtoToDocument({
            ...documentFixtures[0],
            supplemental_metadata: {
                ...documentFixtures[0].supplemental_metadata,
                visibility_scope: 'internal',
            },
        })

        expect(getDocumentTrustState(document)).toMatchObject({
            tone: 'brand',
            title: 'Trusted internal source',
        })
    })

    it('formats document metadata labels and tones consistently', () => {
        expect(formatStatusLabel('pending_review')).toBe('pending review')
        expect(getLifecycleTone('approved')).toBe('success')
        expect(getLifecycleTone('draft')).toBe('neutral')
        expect(getProcessingTone('completed')).toBe('success')
        expect(getProcessingTone('extracting')).toBe('brand')
        expect(getProcessingTone('pending')).toBe('neutral')
        expect(getVisibilityTone('public')).toBe('brand')
        expect(getVisibilityTone('internal')).toBe('neutral')
    })
})
