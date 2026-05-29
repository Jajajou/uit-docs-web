import { apiClient } from '@/shared/api/client'
import { mapJobDtoToJob } from '@/entities/jobs/mappers'
import type { Job, JobDto } from '@/entities/jobs/types'

export async function getJobs(params?: { scenario?: string }): Promise<Job[]> {
    const response = await apiClient.get<{ jobs: JobDto[] }>('/jobs', {
        params,
    })

    return response.data.jobs.map(mapJobDtoToJob)
}

export async function retryJob(id: string, params?: { scenario?: string }): Promise<Job> {
    const response = await apiClient.post<{ job: JobDto }>(`/jobs/${id}/retry`, undefined, {
        params,
    })

    return mapJobDtoToJob(response.data.job)
}
