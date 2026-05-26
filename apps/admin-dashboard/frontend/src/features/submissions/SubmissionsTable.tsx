import { Link } from 'react-router-dom'
import { ArrowRight, FileStack } from 'lucide-react'
import { useSubmissionsQuery } from '@/entities/submissions/queries'
import { DataTable } from '@/shared/ui/composites/DataTable'
import { Badge } from '@/shared/ui/primitives/Badge'
import { formatDateTime } from '@/shared/lib/format'

export function SubmissionsTable({ scenario }: { scenario?: string }) {
    const submissionsQuery = useSubmissionsQuery({ scenario })

    if (submissionsQuery.isError) {
        return <div className="rounded-2xl border border-error-200 bg-error-50 p-4 text-sm text-error-700 dark:border-error-800 dark:bg-error-950 dark:text-error-300">{submissionsQuery.error.message}</div>
    }

    return (
        <DataTable
            rows={submissionsQuery.data ?? []}
            getRowKey={(submission) => submission.id}
            isLoading={submissionsQuery.isLoading}
            emptyIcon={FileStack}
            emptyTitle="No submissions yet"
            emptyDescription="Upload flow is ready but there are no pending or approved submissions for this scenario."
            columns={[
                {
                    key: 'title',
                    header: 'Title',
                    render: (submission) => (
                        <Link to={`/portal/submissions/${submission.id}`} className="font-medium text-gray-900 hover:text-brand-700 dark:text-white">
                            {submission.title}
                        </Link>
                    ),
                },
                {
                    key: 'source',
                    header: 'Source',
                    render: (submission) => submission.sourceType,
                },
                {
                    key: 'lifecycle',
                    header: 'Lifecycle',
                    render: (submission) => <Badge tone={submission.lifecycleStatus === 'approved' ? 'success' : 'warning'}>{submission.lifecycleStatus}</Badge>,
                },
                {
                    key: 'processing',
                    header: 'Processing',
                    render: (submission) => <Badge tone={submission.processingStatus === 'completed' ? 'success' : 'brand'}>{submission.processingStatus}</Badge>,
                },
                {
                    key: 'updated',
                    header: 'Updated',
                    render: (submission) => formatDateTime(submission.updatedAt),
                },
            ]}
            mobileCardRender={(submission) => (
                <div className="space-y-4 rounded-[1.5rem] border border-gray-200 bg-white/92 p-4 shadow-theme-xs dark:border-gray-800 dark:bg-[#101a2c]">
                    <div className="space-y-2">
                        <Link
                            to={`/portal/submissions/${submission.id}`}
                            className="inline-flex min-h-11 w-full items-start justify-between gap-3 rounded-2xl text-base font-semibold leading-6 text-gray-950 hover:text-brand-700 dark:text-white"
                        >
                            <span>{submission.title}</span>
                            <ArrowRight className="mt-1 shrink-0" size={16} />
                        </Link>
                        <div className="flex flex-wrap gap-2">
                            <Badge tone={submission.lifecycleStatus === 'approved' ? 'success' : 'warning'}>{submission.lifecycleStatus}</Badge>
                            <Badge tone={submission.processingStatus === 'completed' ? 'success' : 'brand'}>{submission.processingStatus}</Badge>
                            <Badge tone="neutral">{submission.sourceType}</Badge>
                        </div>
                    </div>

                    <div className="flex items-center justify-between gap-3 text-sm text-gray-500 dark:text-gray-300">
                        <span className="font-medium text-gray-600 dark:text-gray-400">Updated</span>
                        <span className="text-right">{formatDateTime(submission.updatedAt)}</span>
                    </div>
                </div>
            )}
        />
    )
}
