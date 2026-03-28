import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { applyReviewDecision, getReviewTasks } from '@/entities/reviews/api'
import type { ReviewDecisionMutationPayload, ReviewTask } from '@/entities/reviews/types'

export function useReviewTasksQuery(params?: { scenario?: string }) {
    return useQuery({
        queryKey: ['reviews', params?.scenario ?? 'happy'],
        queryFn: () => getReviewTasks(params),
    })
}

export function useReviewDecisionMutation(params?: { scenario?: string }) {
    const queryClient = useQueryClient()
    const scenarioKey = params?.scenario ?? 'happy'

    return useMutation({
        mutationFn: ({ reviewId, payload }: { reviewId: string; payload: ReviewDecisionMutationPayload }) =>
            applyReviewDecision(reviewId, payload, params),
        onSuccess: (task) => {
            queryClient.setQueryData(['reviews', scenarioKey], (current: ReviewTask[] | undefined) =>
                (current ?? []).map((entry) => (entry.id === task.id ? task : entry)),
            )
            queryClient.invalidateQueries({ queryKey: ['submissions'] })
            queryClient.invalidateQueries({ queryKey: ['documents'] })
        },
    })
}
