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

    it('requires a file when the source type is file', () => {
        const result = validateUploadDraft({
            ...baseValues,
            fileCount: 0,
        })

        expect(result.success).toBe(false)

        if (!result.success) {
            expect(result.error.issues.some((issue) => issue.path[0] === 'fileCount')).toBe(true)
        }
    })

    it('requires a valid source URL when the source type is url', () => {
        const result = validateUploadDraft({
            ...baseValues,
            sourceType: 'url',
            fileCount: 0,
            url: 'not-a-valid-url',
        })

        expect(result.success).toBe(false)

        if (!result.success) {
            expect(result.error.issues.some((issue) => issue.path[0] === 'url')).toBe(true)
        }
    })

    it('requires both ownership confirmations before review entry', () => {
        const result = validateUploadDraft({
            ...baseValues,
            confirmOwnership: false,
            confirmReviewReady: false,
        })

        expect(result.success).toBe(false)

        if (!result.success) {
            expect(result.error.issues.some((issue) => issue.path[0] === 'confirmOwnership')).toBe(true)
            expect(result.error.issues.some((issue) => issue.path[0] === 'confirmReviewReady')).toBe(true)
        }
    })
})
