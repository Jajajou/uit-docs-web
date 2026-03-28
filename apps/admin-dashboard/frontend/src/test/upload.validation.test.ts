import { describe, expect, it } from 'vitest'
import { parseTagInput, validateUploadDraft, type UploadDraftFormValues } from '@/features/uploads/schema'

const baseValues: UploadDraftFormValues = {
    sourceType: 'file',
    title: 'Thong bao hoc phi hoc ky 2',
    fileCount: 1,
    rawText: '',
    url: '',
    issuingUnit: 'Phong Dao tao Dai hoc',
    visibilityScope: 'internal',
    tagsInput: 'hoc-phi, sinh-vien',
    notes: '',
    confirmOwnership: true,
    confirmReviewReady: true,
}

describe('upload draft validation', () => {
    it('accepts a valid file submission draft', () => {
        const result = validateUploadDraft(baseValues)

        expect(result.success).toBe(true)

        if (result.success) {
            expect(result.data.tags).toEqual(['hoc-phi', 'sinh-vien'])
        }
    })

    it('requires enough raw text when source type is text', () => {
        const result = validateUploadDraft({
            ...baseValues,
            sourceType: 'text',
            fileCount: 0,
            rawText: 'Too short',
        })

        expect(result.success).toBe(false)

        if (!result.success) {
            expect(result.error.issues.some((issue) => issue.path[0] === 'rawText')).toBe(true)
        }
    })

    it('deduplicates and trims tags', () => {
        expect(parseTagInput(' hoc-phi, sinh-vien, hoc-phi , ')).toEqual(['hoc-phi', 'sinh-vien'])
    })
})
