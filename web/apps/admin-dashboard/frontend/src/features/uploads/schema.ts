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
        title: z.string().trim().min(8, 'Tiêu đề phải có ít nhất 8 ký tự.').max(120, 'Tiêu đề quá dài.'),
        fileCount: z.number().int().nonnegative(),
        rawText: z.string().trim(),
        url: z.string().trim(),
        issuingUnit: z.string().trim().min(4, 'Đơn vị ban hành là bắt buộc.').max(120, 'Tên đơn vị ban hành quá dài.'),
        visibilityScope: z.enum(['public', 'internal']),
        tagsInput: z.string().trim().max(200, 'Danh sách nhãn quá dài.'),
        notes: z.string().trim().max(400, 'Ghi chú không được vượt quá 400 ký tự.'),
        confirmOwnership: z.boolean(),
        confirmReviewReady: z.boolean(),
    })
    .superRefine((values, context) => {
        if (values.sourceType === 'file' && values.fileCount < 1) {
            context.addIssue({
                code: z.ZodIssueCode.custom,
                message: 'Hãy đính kèm ít nhất một tệp trước khi gửi.',
                path: ['fileCount'],
            })
        }

        if (values.sourceType === 'text' && values.rawText.length < 80) {
            context.addIssue({
                code: z.ZodIssueCode.custom,
                message: 'Văn bản nguồn cần đủ ngữ cảnh để trích xuất, tối thiểu 80 ký tự.',
                path: ['rawText'],
            })
        }

        if (values.sourceType === 'url') {
            const result = z.string().url('Hãy nhập liên kết nguồn hợp lệ.').safeParse(values.url)

            if (!result.success) {
                context.addIssue({
                    code: z.ZodIssueCode.custom,
                    message: 'Hãy nhập liên kết nguồn hợp lệ.',
                    path: ['url'],
                })
            }
        }

        if (!values.confirmOwnership) {
            context.addIssue({
                code: z.ZodIssueCode.custom,
                message: 'Bạn cần xác nhận đây là nguồn chính thức trước khi chuyển duyệt.',
                path: ['confirmOwnership'],
            })
        }

        if (!values.confirmReviewReady) {
            context.addIssue({
                code: z.ZodIssueCode.custom,
                message: 'Bạn cần xác nhận tài liệu đã sẵn sàng vào hàng duyệt.',
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
