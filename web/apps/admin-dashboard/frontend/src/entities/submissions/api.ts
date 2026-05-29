import { apiClient } from '@/shared/api/client'
import { mapSubmissionDtoToSubmission } from '@/entities/submissions/mappers'
import type { Submission, SubmissionDto, UploadMutationPayload } from '@/entities/submissions/types'

const UPLOAD_REQUEST_TIMEOUT_MS = 90000

export async function getSubmissions(params?: { scenario?: string }): Promise<Submission[]> {
    const response = await apiClient.get<{ submissions: SubmissionDto[] }>('/submissions', {
        params,
    })

    return response.data.submissions.map(mapSubmissionDtoToSubmission)
}

export async function getSubmissionById(id: string, params?: { scenario?: string }): Promise<Submission> {
    const response = await apiClient.get<{ submission: SubmissionDto }>(`/submissions/${id}`, {
        params,
    })

    return mapSubmissionDtoToSubmission(response.data.submission)
}

export async function createUploadSubmission(
    endpoint: '/uploads/file' | '/uploads/text' | '/uploads/url',
    payload: UploadMutationPayload,
    params?: { scenario?: string },
): Promise<Submission> {
    const response = await apiClient.post<{ submission: SubmissionDto }>(endpoint, payload, {
        params,
        timeout: UPLOAD_REQUEST_TIMEOUT_MS,
    })

    return mapSubmissionDtoToSubmission(response.data.submission)
}

export async function createMultipartUploadSubmission(
    file: File,
    payload: UploadMutationPayload,
    params?: { scenario?: string },
): Promise<Submission> {
    const formData = new FormData()
    formData.set('file', file)
    formData.set('title', payload.title)
    formData.set('visibility_scope', payload.visibilityScope)
    formData.set('notes', payload.notes)
    formData.set('issuing_unit', payload.issuingUnit)
    if (payload.tags.length > 0) {
        formData.set('tags', payload.tags.join(','))
    }

    const response = await apiClient.post<{ submission: SubmissionDto }>('/uploads/file/multipart', formData, {
        params,
        timeout: UPLOAD_REQUEST_TIMEOUT_MS,
    })

    return mapSubmissionDtoToSubmission(response.data.submission)
}
