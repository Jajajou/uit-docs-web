import { useDeferredValue, useMemo, useState } from 'react'
import { Activity } from 'lucide-react'
import { toast } from 'sonner'
import { useSessionQuery } from '@/entities/auth/queries'
import { useJobsQuery, useRetryJobMutation } from '@/entities/jobs/queries'
import type { Job } from '@/entities/jobs/types'
import { formatDateTime } from '@/shared/lib/format'
import { Badge, Button, Card, FilterBar, Select } from '@/shared/ui'
import { DataTable } from '@/shared/ui/composites/DataTable'

type JobStatusFilter = 'all' | Job['status']

const statusOptions = [
    { label: 'All statuses', value: 'all' },
    { label: 'Completed', value: 'completed' },
    { label: 'Failed', value: 'failed' },
    { label: 'Indexing', value: 'indexing' },
    { label: 'Uploading', value: 'uploading' },
    { label: 'Pending', value: 'pending' },
]

function getJobStatusTone(status: Job['status']) {
    switch (status) {
        case 'completed':
            return 'success' as const
        case 'failed':
            return 'danger' as const
        case 'indexing':
        case 'extracting':
        case 'uploading':
            return 'brand' as const
        default:
            return 'warning' as const
    }
}

export function JobsTable({ scenario }: { scenario?: string }) {
    const jobsQuery = useJobsQuery({ scenario })
    const sessionQuery = useSessionQuery({ scenario })
    const retryJobMutation = useRetryJobMutation({ scenario })
    const [searchValue, setSearchValue] = useState('')
    const [statusFilter, setStatusFilter] = useState<JobStatusFilter>('all')
    const deferredSearch = useDeferredValue(searchValue)

    const filteredJobs = useMemo(() => {
        const normalizedSearch = deferredSearch.trim().toLowerCase()

        return (jobsQuery.data ?? []).filter((job) => {
            const matchesSearch =
                normalizedSearch.length === 0 ||
                job.relatedTitle.toLowerCase().includes(normalizedSearch) ||
                job.type.toLowerCase().includes(normalizedSearch) ||
                job.message.toLowerCase().includes(normalizedSearch)

            const matchesStatus = statusFilter === 'all' || job.status === statusFilter

            return matchesSearch && matchesStatus
        })
    }, [deferredSearch, jobsQuery.data, statusFilter])

    const jobCounts = jobsQuery.data ?? []
    const isAdminBreakGlass = sessionQuery.data?.user.role === 'admin'

    if (jobsQuery.isError) {
        return <div className="rounded-2xl border border-error-200 bg-error-50 p-4 text-sm text-error-700 dark:border-error-800 dark:bg-error-950 dark:text-error-300">{jobsQuery.error.message}</div>
    }

    return (
        <div className="space-y-4">
            {isAdminBreakGlass ? (
                <Card className="space-y-2 border-warning-200 bg-warning-50 dark:border-warning-800 dark:bg-warning-950">
                    <div className="text-sm font-semibold text-warning-900 dark:text-warning-100">Break-glass support mode</div>
                    <p className="text-sm text-warning-800 dark:text-warning-200">
                        Job retry remains an operator-owned remediation flow. As `admin`, you are using an audited support override intended for incident recovery only.
                    </p>
                </Card>
            ) : null}
            <div className="grid gap-4 md:grid-cols-3">
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Active jobs</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">
                        {jobCounts.filter((job) => job.status !== 'completed').length}
                    </div>
                </Card>
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Failed jobs</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">
                        {jobCounts.filter((job) => job.status === 'failed').length}
                    </div>
                </Card>
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Completed jobs</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">
                        {jobCounts.filter((job) => job.status === 'completed').length}
                    </div>
                </Card>
            </div>

            <FilterBar
                searchValue={searchValue}
                onSearchChange={setSearchValue}
                searchPlaceholder="Search by related title, job type or message..."
                actions={
                    <div className="min-w-56">
                        <Select
                            aria-label="Filter by job status"
                            options={statusOptions}
                            value={statusFilter}
                            onChange={(event) => setStatusFilter(event.target.value as JobStatusFilter)}
                        />
                    </div>
                }
            />

            <DataTable
                rows={filteredJobs}
                getRowKey={(job) => job.id}
                isLoading={jobsQuery.isLoading}
                emptyIcon={Activity}
                emptyTitle="No jobs to show"
                emptyDescription="Try a broader search or change the status filter."
                columns={[
                    { key: 'type', header: 'Type', render: (job) => job.type },
                    {
                        key: 'title',
                        header: 'Related title',
                        render: (job) => (
                            <div className="space-y-1">
                                <div className="font-medium text-gray-900 dark:text-white">{job.relatedTitle}</div>
                                <div className="text-xs text-gray-500">{job.message}</div>
                            </div>
                        ),
                    },
                    {
                        key: 'status',
                        header: 'Status',
                        render: (job) => <Badge tone={getJobStatusTone(job.status)}>{job.status}</Badge>,
                    },
                    { key: 'progress', header: 'Progress', render: (job) => `${job.progress}%` },
                    { key: 'updated', header: 'Updated', render: (job) => formatDateTime(job.updatedAt) },
                    {
                        key: 'actions',
                        header: 'Action',
                        render: (job) =>
                            job.status === 'failed' ? (
                                <Button
                                    variant="outline"
                                    size="sm"
                                    isLoading={retryJobMutation.isPending && retryJobMutation.variables === job.id}
                                    onClick={async () => {
                                        try {
                                            const updatedJob = await retryJobMutation.mutateAsync(job.id)
                                            toast.success(`Retry accepted for ${job.relatedTitle}`, {
                                                description: isAdminBreakGlass ? `${updatedJob.message} Admin support override was recorded.` : updatedJob.message,
                                            })
                                        } catch (error) {
                                            const message = error instanceof Error ? error.message : 'Unable to retry this job.'
                                            toast.error('Retry failed', {
                                                description: message,
                                            })
                                        }
                                    }}
                                >
                                    {isAdminBreakGlass ? 'Retry (support override)' : 'Retry'}
                                </Button>
                            ) : (
                                <Badge tone="neutral">Watching</Badge>
                            ),
                    },
                ]}
            />
        </div>
    )
}
