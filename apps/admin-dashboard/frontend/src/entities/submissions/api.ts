import { apiClient } from '@/shared/api/client'
import { mapSubmissionDtoToSubmission } from '@/entities/submissions/mappers'
import type { Submission, SubmissionDto, UploadMutationPayload } from '@/entities/submissions/types'

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
    })

    return mapSubmissionDtoToSubmission(response.data.submission)
}
