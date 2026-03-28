import { z } from 'zod'
import type { VisibilityScope } from '@/entities/documents/types'
import type { UploadSourceType } from '@/entities/submissions/types'

export interface UploadDraftFormValues {
    sourceType: UploadSourceType
    title: string
    fileCount: number
    rawText: string
    url: string
    issuingUnit: string
    visibilityScope: VisibilityScope
    tagsInput: string
    notes: string
    confirmOwnership: boolean
    confirmReviewReady: boolean
}

export interface ValidatedUploadDraft {
    sourceType: UploadSourceType
    title: string
    rawText: string
    url: string
    issuingUnit: string
    visibilityScope: VisibilityScope
    tags: string[]
    notes: string
    confirmOwnership: true
    confirmReviewReady: true
}

const uploadDraftSchema = z
    .object({
        sourceType: z.enum(['file', 'text', 'url']),
        title: z.string().trim().min(8, 'Title should be at least 8 characters.').max(120, 'Title is too long.'),
        fileCount: z.number().int().nonnegative(),
        rawText: z.string().trim(),
        url: z.string().trim(),
        issuingUnit: z.string().trim().min(4, 'Issuing unit is required.').max(120, 'Issuing unit is too long.'),
        visibilityScope: z.enum(['public', 'internal']),
        tagsInput: z.string().trim().max(200, 'Tags list is too long.'),
        notes: z.string().trim().max(400, 'Notes should stay under 400 characters.'),
        confirmOwnership: z.boolean(),
        confirmReviewReady: z.boolean(),
    })
    .superRefine((values, context) => {
        if (values.sourceType === 'file' && values.fileCount < 1) {
            context.addIssue({
                code: z.ZodIssueCode.custom,
                message: 'Attach at least one file before submitting.',
                path: ['fileCount'],
            })
        }

        if (values.sourceType === 'text' && values.rawText.length < 80) {
            context.addIssue({
                code: z.ZodIssueCode.custom,
                message: 'Raw text should include enough context for extraction, at least 80 characters.',
                path: ['rawText'],
            })
        }

        if (values.sourceType === 'url') {
            const result = z.string().url('Provide a valid source URL.').safeParse(values.url)

            if (!result.success) {
                context.addIssue({
                    code: z.ZodIssueCode.custom,
                    message: 'Provide a valid source URL.',
                    path: ['url'],
                })
            }
        }

        if (!values.confirmOwnership) {
            context.addIssue({
                code: z.ZodIssueCode.custom,
                message: 'You must confirm the source is official before review.',
                path: ['confirmOwnership'],
            })
        }

        if (!values.confirmReviewReady) {
            context.addIssue({
                code: z.ZodIssueCode.custom,
                message: 'You must confirm the document can enter the review queue.',
                path: ['confirmReviewReady'],
            })
        }
    })

export function parseTagInput(value: string) {
    return Array.from(
        new Set(
            value
                .split(',')
                .map((tag) => tag.trim())
                .filter(Boolean),
        ),
    )
}

export function validateUploadDraft(values: UploadDraftFormValues) {
    const result = uploadDraftSchema.safeParse(values)

    if (!result.success) {
        return result
    }

    const data: ValidatedUploadDraft = {
        sourceType: result.data.sourceType,
        title: result.data.title,
        rawText: result.data.rawText,
        url: result.data.url,
        issuingUnit: result.data.issuingUnit,
        visibilityScope: result.data.visibilityScope,
        tags: parseTagInput(result.data.tagsInput),
        notes: result.data.notes,
        confirmOwnership: true,
        confirmReviewReady: true,
    }

    return {
        success: true as const,
        data,
    }
}
