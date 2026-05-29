import { apiClient } from '@/shared/api/client'
import { mapReviewTaskDtoToReviewTask } from '@/entities/reviews/mappers'
import type { ReviewDecisionMutationPayload, ReviewTask, ReviewTaskDto } from '@/entities/reviews/types'

export async function getReviewTasks(params?: { scenario?: string }): Promise<ReviewTask[]> {
    const response = await apiClient.get<{ tasks: ReviewTaskDto[] }>('/reviews', {
        params,
    })

    return response.data.tasks.map(mapReviewTaskDtoToReviewTask)
}

export async function applyReviewDecision(
    reviewId: string,
    payload: ReviewDecisionMutationPayload,
    params?: { scenario?: string },
): Promise<ReviewTask> {
    const response = await apiClient.post<{ task: ReviewTaskDto }>(`/reviews/${reviewId}/decision`, {
        status: payload.status,
        reason: payload.reason,
        edited_temporal_metadata: payload.editedTemporalMetadata,
    }, {
        params,
    })

    return mapReviewTaskDtoToReviewTask(response.data.task)
}
