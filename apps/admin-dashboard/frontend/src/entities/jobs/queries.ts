import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getJobs, retryJob } from '@/entities/jobs/api'
import type { Job } from '@/entities/jobs/types'

export function useJobsQuery(params?: { scenario?: string }) {
    return useQuery({
        queryKey: ['jobs', params?.scenario ?? 'happy'],
        queryFn: () => getJobs(params),
    })
}

export function useRetryJobMutation(params?: { scenario?: string }) {
    const queryClient = useQueryClient()
    const scenarioKey = params?.scenario ?? 'happy'

    return useMutation({
        mutationFn: (id: string) => retryJob(id, params),
        onSuccess: (job) => {
            queryClient.setQueryData(['jobs', scenarioKey], (current: Job[] | undefined) =>
                (current ?? []).map((entry) => (entry.id === job.id ? job : entry)),
            )
        },
    })
}
