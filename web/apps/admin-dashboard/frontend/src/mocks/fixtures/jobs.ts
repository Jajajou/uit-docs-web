import type { JobDto } from '@/entities/jobs/types'

export const jobFixtures: JobDto[] = [
    {
        id: 'job-001',
        type: 'upload',
        status: 'completed',
        progress: 100,
        related_title: 'Quy dinh hoc vu 2024-2025',
        started_at: '2026-03-16T08:28:00.000Z',
        updated_at: '2026-03-16T08:31:00.000Z',
        message: 'Upload completed successfully.',
    },
    {
        id: 'job-002',
        type: 'indexing',
        status: 'failed',
        progress: 62,
        related_title: 'Quy trinh xin tam hoan hoc phi',
        started_at: '2026-03-19T01:20:00.000Z',
        updated_at: '2026-03-19T01:23:00.000Z',
        message: 'Embedding step failed. Retry available.',
    },
    {
        id: 'job-003',
        type: 'scan',
        status: 'indexing',
        progress: 48,
        related_title: 'UIT public bulletin crawl',
        started_at: '2026-03-20T02:00:00.000Z',
        updated_at: '2026-03-20T02:12:00.000Z',
        message: 'Scanning source pages and scheduling updates.',
    },
]
