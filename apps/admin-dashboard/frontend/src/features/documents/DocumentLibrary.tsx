import { useDeferredValue, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen } from 'lucide-react'
import { useDocumentsQuery } from '@/entities/documents/queries'
import type { DocumentLifecycleStatus, VisibilityScope } from '@/entities/documents/types'
import { formatDateTime } from '@/shared/lib/format'
import { Badge, Card, FilterBar, Select } from '@/shared/ui'
import { DataTable } from '@/shared/ui/composites/DataTable'

type LifecycleFilter = 'all' | 'approved' | 'pending_review' | 'archived'
type VisibilityFilter = 'all' | 'public' | 'internal'

const lifecycleLabelMap: Record<DocumentLifecycleStatus, string> = {
    approved: 'Đã duyệt',
    pending_review: 'Chờ rà soát',
    rejected: 'Không duyệt',
    archived: 'Đã lưu trữ',
    draft: 'Bản nháp',
}

const visibilityLabelMap: Record<VisibilityScope, string> = {
    public: 'Công khai',
    internal: 'Nội bộ',
}

const lifecycleOptions = [
    { label: 'Tất cả trạng thái', value: 'all' },
    { label: 'Đã duyệt', value: 'approved' },
    { label: 'Chờ rà soát', value: 'pending_review' },
    { label: 'Đã lưu trữ', value: 'archived' },
]

const visibilityOptions = [
    { label: 'Tất cả phạm vi', value: 'all' },
    { label: 'Công khai', value: 'public' },
    { label: 'Nội bộ', value: 'internal' },
]

function formatLifecycleLabel(status: DocumentLifecycleStatus) {
    return lifecycleLabelMap[status] ?? status
}

function formatVisibilityLabel(scope: VisibilityScope) {
    return visibilityLabelMap[scope] ?? scope
}

function getLifecycleTone(status: DocumentLifecycleStatus) {
    if (status === 'approved') {
        return 'success' as const
    }

    if (status === 'pending_review') {
        return 'warning' as const
    }

    if (status === 'archived') {
        return 'neutral' as const
    }

    return 'danger' as const
}

function getVisibilityTone(scope: VisibilityScope) {
    return scope === 'public' ? ('brand' as const) : ('neutral' as const)
}

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
                document.supplemental.issuingUnit.toLowerCase().includes(normalizedSearch) ||
                document.temporal.documentType.toLowerCase().includes(normalizedSearch)

            const matchesLifecycle = lifecycleFilter === 'all' || document.lifecycleStatus === lifecycleFilter
            const matchesVisibility =
                visibilityFilter === 'all' || document.supplemental.visibilityScope === visibilityFilter

            return matchesSearch && matchesLifecycle && matchesVisibility
        })
    }, [deferredSearch, documentsQuery.data, lifecycleFilter, visibilityFilter])

    const documentCounts = documentsQuery.data ?? []

    if (documentsQuery.isError) {
        return (
            <div className="rounded-2xl border border-error-200 bg-error-50 p-4 text-sm text-error-700 dark:border-error-800 dark:bg-error-950 dark:text-error-300">
                {documentsQuery.error.message}
            </div>
        )
    }

    return (
        <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Tổng tài liệu</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">{documentCounts.length}</div>
                </Card>
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Sẵn sàng trích dẫn</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">
                        {documentCounts.filter((document) => document.supplemental.visibilityScope === 'public').length}
                    </div>
                </Card>
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Đã lưu trữ</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">
                        {documentCounts.filter((document) => document.system.isArchived).length}
                    </div>
                </Card>
            </div>

            <FilterBar
                searchValue={searchValue}
                onSearchChange={setSearchValue}
                searchPlaceholder="Tìm theo tên, đơn vị ban hành hoặc loại tài liệu..."
                actions={
                    <>
                        <div className="min-w-56">
                            <Select
                                aria-label="Lọc theo trạng thái"
                                options={lifecycleOptions}
                                value={lifecycleFilter}
                                onChange={(event) => setLifecycleFilter(event.target.value as LifecycleFilter)}
                            />
                        </div>
                        <div className="min-w-56">
                            <Select
                                aria-label="Lọc theo phạm vi"
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
                emptyTitle="Chưa có tài liệu phù hợp"
                emptyDescription="Hãy thử nới điều kiện lọc hoặc tìm kiếm theo từ khóa khác."
                columns={[
                    {
                        key: 'title',
                        header: 'Tài liệu',
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
                        key: 'lifecycle',
                        header: 'Trạng thái',
                        render: (document) => (
                            <Badge tone={getLifecycleTone(document.lifecycleStatus)}>
                                {formatLifecycleLabel(document.lifecycleStatus)}
                            </Badge>
                        ),
                    },
                    {
                        key: 'visibility',
                        header: 'Phạm vi',
                        render: (document) => (
                            <Badge tone={getVisibilityTone(document.supplemental.visibilityScope)}>
                                {formatVisibilityLabel(document.supplemental.visibilityScope)}
                            </Badge>
                        ),
                    },
                    {
                        key: 'academicYear',
                        header: 'Năm học',
                        render: (document) => document.temporal.academicYear ?? 'Chưa cập nhật',
                    },
                    {
                        key: 'updated',
                        header: 'Cập nhật',
                        render: (document) => formatDateTime(document.updatedAt),
                    },
                ]}
            />
        </div>
    )
}
