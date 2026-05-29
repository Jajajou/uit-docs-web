import type { Job, JobDto } from '@/entities/jobs/types'

export function mapJobDtoToJob(dto: JobDto): Job {
    return {
        id: dto.id,
        type: dto.type,
        status: dto.status,
        progress: dto.progress,
        relatedTitle: dto.related_title,
        startedAt: dto.started_at,
        updatedAt: dto.updated_at,
        message: dto.message,
    }
}
