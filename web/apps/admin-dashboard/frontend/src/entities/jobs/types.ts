import type { ProcessingStatus } from '@/entities/documents/types'

export type JobType = 'upload' | 'indexing' | 'scan'

export interface Job {
    id: string
    type: JobType
    status: ProcessingStatus
    progress: number
    relatedTitle: string
    startedAt: string
    updatedAt: string
    message: string
}

export interface JobDto {
    id: string
    type: JobType
    status: ProcessingStatus
    progress: number
    related_title: string
    started_at: string
    updated_at: string
    message: string
}
