import { useDeferredValue, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen } from 'lucide-react'
import { formatStatusLabel, getLifecycleTone, getVisibilityTone } from '@/entities/documents/presentation'
import { useDocumentsQuery } from '@/entities/documents/queries'
import { formatDateTime } from '@/shared/lib/format'
import { Badge, Card, FilterBar, Select } from '@/shared/ui'
import { DataTable } from '@/shared/ui/composites/DataTable'

type LifecycleFilter = 'all' | 'approved' | 'pending_review' | 'archived'
type VisibilityFilter = 'all' | 'public' | 'internal'

const lifecycleOptions = [
    { label: 'All lifecycle states', value: 'all' },
    { label: 'Approved', value: 'approved' },
    { label: 'Pending review', value: 'pending_review' },
    { label: 'Archived', value: 'archived' },
]

const visibilityOptions = [
    { label: 'All visibility scopes', value: 'all' },
    { label: 'Public', value: 'public' },
    { label: 'Internal', value: 'internal' },
]

export function DocumentLibrary({ scenario }: { scenario?: string }) {
    const documentsQuery = useDocumentsQuery({ scenario })
    const [searchValue, setSearchValue] = useState('')
    const [lifecycleFilter, setLifecycleFilter] = useState<LifecycleFilter>('all')
    const [visibilityFilter, setVisibilityFilter] = useState<VisibilityFilter>('all')
    const deferredSearch = useDeferredValue(searchValue)

    const filteredDocuments = useMemo(() => {
        const normalizedSearch = deferredSearch.trim().toLowerCase()

        return (documentsQuery.data ?? []).filter((document) => {
            const matchesSearch =
                normalizedSearch.length === 0 ||
                document.title.toLowerCase().includes(normalizedSearch) ||
                document.ownerName.toLowerCase().includes(normalizedSearch) ||
                document.temporal.documentType.toLowerCase().includes(normalizedSearch)

            const matchesLifecycle = lifecycleFilter === 'all' || document.lifecycleStatus === lifecycleFilter
            const matchesVisibility =
                visibilityFilter === 'all' || document.supplemental.visibilityScope === visibilityFilter

            return matchesSearch && matchesLifecycle && matchesVisibility
        })
    }, [deferredSearch, documentsQuery.data, lifecycleFilter, visibilityFilter])

    const documentCounts = documentsQuery.data ?? []

    if (documentsQuery.isError) {
        return <div className="rounded-2xl border border-error-200 bg-error-50 p-4 text-sm text-error-700 dark:border-error-800 dark:bg-error-950 dark:text-error-300">{documentsQuery.error.message}</div>
    }

    return (
        <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Total documents</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">{documentCounts.length}</div>
                </Card>
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Public ready</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">
                        {documentCounts.filter((document) => document.supplemental.visibilityScope === 'public').length}
                    </div>
                </Card>
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Archived</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">
                        {documentCounts.filter((document) => document.system.isArchived).length}
                    </div>
                </Card>
            </div>

            <FilterBar
                searchValue={searchValue}
                onSearchChange={setSearchValue}
                searchPlaceholder="Search by title, owner or document type..."
                actions={
                    <>
                        <div className="min-w-56">
                            <Select
                                aria-label="Filter by lifecycle"
                                options={lifecycleOptions}
                                value={lifecycleFilter}
                                onChange={(event) => setLifecycleFilter(event.target.value as LifecycleFilter)}
                            />
                        </div>
                        <div className="min-w-56">
                            <Select
                                aria-label="Filter by visibility"
                                options={visibilityOptions}
                                value={visibilityFilter}
                                onChange={(event) => setVisibilityFilter(event.target.value as VisibilityFilter)}
                            />
                        </div>
                    </>
                }
            />

            <DataTable
                rows={filteredDocuments}
                getRowKey={(document) => document.id}
                isLoading={documentsQuery.isLoading}
                emptyIcon={BookOpen}
                emptyTitle="No documents found"
                emptyDescription="Try a broader search or reset the lifecycle and visibility filters."
                columns={[
                    {
                        key: 'title',
                        header: 'Document',
                        render: (document) => (
                            <div className="space-y-1">
                                <Link to={`/documents/${document.id}`} className="font-medium text-gray-900 hover:text-brand-700 dark:text-white">
                                    {document.title}
                                </Link>
                                <div className="text-xs text-gray-500">{document.supplemental.issuingUnit}</div>
                            </div>
                        ),
                    },
                    {
                        key: 'owner',
                        header: 'Owner',
                        render: (document) => document.ownerName,
                    },
                    {
                        key: 'lifecycle',
                        header: 'Lifecycle',
                        render: (document) => (
                            <Badge tone={getLifecycleTone(document.lifecycleStatus)}>{formatStatusLabel(document.lifecycleStatus)}</Badge>
                        ),
                    },
                    {
                        key: 'visibility',
                        header: 'Visibility',
                        render: (document) => (
                            <Badge tone={getVisibilityTone(document.supplemental.visibilityScope)}>
                                {document.supplemental.visibilityScope}
                            </Badge>
                        ),
                    },
                    {
                        key: 'type',
                        header: 'Type',
                        render: (document) => document.temporal.documentType,
                    },
                    {
                        key: 'updated',
                        header: 'Updated',
                        render: (document) => formatDateTime(document.updatedAt),
                    },
                ]}
            />
        </div>
    )
}
