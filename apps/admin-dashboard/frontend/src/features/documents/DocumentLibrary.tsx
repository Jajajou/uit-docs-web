import { useDeferredValue, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, BookOpen, FileSearch, Sparkles } from 'lucide-react'
import { RouteIntentLink } from '@/app/router/RouteIntentLink'
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

function normalizeSearchValue(value: string) {
    return value
        .replace(/[đĐ]/g, (character) => (character === 'Đ' ? 'D' : 'd'))
        .normalize('NFD')
        .replace(/\p{Diacritic}/gu, '')
        .toLowerCase()
}

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
        const normalizedSearch = normalizeSearchValue(deferredSearch.trim())

        return (documentsQuery.data ?? [])
            .filter((document) => {
                const matchesSearch =
                    normalizedSearch.length === 0 ||
                    normalizeSearchValue(document.title).includes(normalizedSearch) ||
                    normalizeSearchValue(document.supplemental.issuingUnit).includes(normalizedSearch) ||
                    normalizeSearchValue(document.temporal.documentType).includes(normalizedSearch)

                const matchesLifecycle = lifecycleFilter === 'all' || document.lifecycleStatus === lifecycleFilter
                const matchesVisibility =
                    visibilityFilter === 'all' || document.supplemental.visibilityScope === visibilityFilter

                return matchesSearch && matchesLifecycle && matchesVisibility
            })
            .sort((left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime())
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

            <Card className="overflow-hidden border-brand-100 bg-[radial-gradient(circle_at_top_left,_rgba(219,234,254,0.95),_rgba(255,255,255,0.98)_42%,_rgba(248,250,252,0.95)_100%)] dark:border-brand-900/70 dark:bg-[radial-gradient(circle_at_top_left,_rgba(12,74,110,0.48),_rgba(10,18,32,0.96)_42%,_rgba(8,15,28,0.98)_100%)]">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div className="space-y-3">
                        <Badge tone="brand" className="w-fit">
                            <Sparkles size={14} />
                            Gợi ý thao tác nhanh
                        </Badge>
                        <div className="space-y-1.5">
                            <h2 className="text-lg font-semibold text-gray-950 dark:text-white">Thu hẹp tài liệu trước, rồi hỏi tiếp trong chat khi cần đối chiếu.</h2>
                            <p className="max-w-2xl text-sm leading-6 text-gray-600 dark:text-gray-300">
                                Bộ lọc ở đây phù hợp cho lúc bạn muốn rà nhanh văn bản mới nhất. Khi cần câu trả lời có dẫn nguồn,
                                bạn có thể nhảy sang chat ngay mà vẫn giữ cùng ngữ cảnh tra cứu.
                            </p>
                        </div>
                    </div>

                    <RouteIntentLink
                        to="/chat"
                        className="inline-flex items-center justify-center gap-2 rounded-[1.2rem] border border-brand-200 bg-white/92 px-4 py-3 text-sm font-semibold text-brand-700 shadow-theme-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-theme-sm dark:border-brand-800 dark:bg-brand-950/35 dark:text-brand-200"
                    >
                        <FileSearch size={16} />
                        Mở chat tham chiếu
                        <ArrowRight size={16} />
                    </RouteIntentLink>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                    <button
                        type="button"
                        onClick={() => setVisibilityFilter('public')}
                        className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white/92 px-3 py-2 text-sm font-medium text-gray-600 transition-all duration-200 hover:border-brand-200 hover:text-brand-700 dark:border-gray-700 dark:bg-gray-900/92 dark:text-gray-200 dark:hover:border-brand-800 dark:hover:text-brand-200"
                    >
                        Chỉ xem công khai
                    </button>
                    <button
                        type="button"
                        onClick={() => setLifecycleFilter('approved')}
                        className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white/92 px-3 py-2 text-sm font-medium text-gray-600 transition-all duration-200 hover:border-brand-200 hover:text-brand-700 dark:border-gray-700 dark:bg-gray-900/92 dark:text-gray-200 dark:hover:border-brand-800 dark:hover:text-brand-200"
                    >
                        Đã duyệt
                    </button>
                    <button
                        type="button"
                        onClick={() => setLifecycleFilter('pending_review')}
                        className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white/92 px-3 py-2 text-sm font-medium text-gray-600 transition-all duration-200 hover:border-brand-200 hover:text-brand-700 dark:border-gray-700 dark:bg-gray-900/92 dark:text-gray-200 dark:hover:border-brand-800 dark:hover:text-brand-200"
                    >
                        Chờ rà soát
                    </button>
                </div>
            </Card>

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
