import { Link } from 'react-router-dom'
import { FileStack } from 'lucide-react'
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
        />
    )
}
