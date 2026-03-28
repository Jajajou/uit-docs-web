import { describe, expect, it } from 'vitest'
import { mapDocumentDtoToDocument } from '@/entities/documents/mappers'
import { getDocumentTrustState } from '@/entities/documents/presentation'
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
})
