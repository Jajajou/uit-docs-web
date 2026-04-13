import { Link } from 'react-router-dom'
import { FileSearch, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { useSessionQuery } from '@/entities/auth/queries'
import { getLifecycleTone, getProcessingTone, getVisibilityTone } from '@/entities/documents/presentation'
import { useArchiveDocumentMutation, useDocumentDetailQuery, useReindexDocumentMutation } from '@/entities/documents/queries'
import type { Document, DocumentLifecycleStatus, VisibilityScope } from '@/entities/documents/types'
import { formatDate, formatDateTime, formatPercent } from '@/shared/lib/format'
import { Badge, Button, Card, EmptyState, MetadataPanel } from '@/shared/ui'

const lifecycleLabelMap: Record<DocumentLifecycleStatus, string> = {
    approved: 'Đã duyệt',
    pending_review: 'Chờ rà soát',
    rejected: 'Không được duyệt',
    archived: 'Đã lưu trữ',
    draft: 'Bản nháp',
}

const visibilityLabelMap: Record<VisibilityScope, string> = {
    public: 'Công khai',
    internal: 'Nội bộ',
}

const documentTypeLabelMap: Record<string, string> = {
    regulation: 'Quy định',
    fee_notice: 'Thông báo học phí',
    announcement: 'Thông báo',
    scholarship: 'Học bổng',
    procedure: 'Quy trình',
    other: 'Tài liệu khác',
}

function formatLifecycleLabel(status: DocumentLifecycleStatus) {
    return lifecycleLabelMap[status] ?? status
}

function formatVisibilityLabel(scope: VisibilityScope) {
    return visibilityLabelMap[scope] ?? scope
}

function formatDocumentType(type: string) {
    return documentTypeLabelMap[type] ?? type
}

function getTrustSummary(document: Document) {
    if (document.system.isArchived || document.lifecycleStatus === 'archived') {
        return {
            title: 'Nguồn lưu trữ',
            description: 'Tài liệu này chỉ nên dùng để đối chiếu lịch sử, không nên xem là quy định hiện hành.',
        }
    }

    if (document.lifecycleStatus === 'pending_review') {
        return {
            title: 'Nguồn đang chờ rà soát',
            description: 'Tài liệu chưa hoàn tất kiểm tra nội bộ. Nếu được trích dẫn, câu trả lời phải kèm cảnh báo rõ ràng.',
        }
    }

    if (document.lifecycleStatus === 'rejected') {
        return {
            title: 'Nguồn không hợp lệ',
            description: 'Tài liệu này đã bị loại khỏi luồng rà soát và không nên dùng cho trả lời chính thức.',
        }
    }

    if (document.supplemental.visibilityScope === 'internal') {
        return {
            title: 'Nguồn nội bộ',
            description: 'Tài liệu chỉ dành cho quy trình nội bộ và không nên xuất hiện như hướng dẫn công khai cho sinh viên.',
        }
    }

    return {
        title: 'Nguồn sẵn sàng trích dẫn',
        description: 'Tài liệu đã qua kiểm tra và có thể dùng làm căn cứ tham chiếu trong UIT AI.',
    }
}

function formatOptionalDate(value: string | null | undefined, fallback = 'Chưa cập nhật') {
    if (!value) {
        return fallback
    }

    return formatDate(value)
}

function formatOptionalDateTime(value: string | null | undefined, fallback = 'Chưa cập nhật') {
    if (!value) {
        return fallback
    }

    return formatDateTime(value)
}

function formatOptionalText(value: string | null | undefined, fallback = 'Chưa cập nhật') {
    return value && value.trim().length > 0 ? value : fallback
}

export function DocumentDetailPanel({ id, scenario }: { id: string; scenario?: string }) {
    const documentQuery = useDocumentDetailQuery(id, { scenario })
    const sessionQuery = useSessionQuery({ scenario })
    const archiveMutation = useArchiveDocumentMutation({ scenario })
    const reindexMutation = useReindexDocumentMutation({ scenario })

    if (documentQuery.isLoading) {
        return <Card className="h-80 animate-pulse" />
    }

    if (documentQuery.isError) {
        return <Card className="text-sm text-error-700 dark:text-error-300">{documentQuery.error.message}</Card>
    }

    if (!documentQuery.data) {
        return (
            <EmptyState
                icon={FileSearch}
                title="Không tìm thấy tài liệu"
                description="Tài liệu này không còn khả dụng hoặc đường dẫn trích dẫn đã thay đổi."
            />
        )
    }

    const document = documentQuery.data
    const isAdminViewer = sessionQuery.data?.user.role === 'admin'
    const currentVersion = document.versionHistory.find((entry) => entry.isCurrent) ?? document.versionHistory[0]
    const trustSummary = getTrustSummary(document)

    const handleArchive = async () => {
        try {
            const updatedDocument = await archiveMutation.mutateAsync(document.id)
            toast.success(`Đã lưu trữ ${updatedDocument.title}`, {
                description: 'Trạng thái tài liệu đã được chuyển sang lưu trữ và ghi nhận trong nhật ký hệ thống.',
            })
        } catch (error) {
            toast.error('Không thể lưu trữ tài liệu', {
                description: error instanceof Error ? error.message : 'Đã xảy ra lỗi khi cập nhật tài liệu.',
            })
        }
    }

    const handleReindex = async () => {
        try {
            const updatedDocument = await reindexMutation.mutateAsync(document.id)
            toast.success(`Đã xếp hàng lập chỉ mục lại cho ${updatedDocument.title}`, {
                description: 'Tài liệu đã được đưa trở lại hàng đợi xử lý.',
            })
        } catch (error) {
            toast.error('Không thể lập chỉ mục lại', {
                description: error instanceof Error ? error.message : 'Đã xảy ra lỗi khi cập nhật tài liệu.',
            })
        }
    }

    return (
        <div className="space-y-6">
            <Card className="space-y-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-3">
                        <div className="flex flex-wrap gap-2">
                            <Badge tone={getLifecycleTone(document.lifecycleStatus)}>{formatLifecycleLabel(document.lifecycleStatus)}</Badge>
                            <Badge tone={getProcessingTone(document.processingStatus)}>
                                {document.processingStatus === 'completed' ? 'Sẵn sàng' : 'Đang xử lý'}
                            </Badge>
                            <Badge tone={getVisibilityTone(document.supplemental.visibilityScope)}>
                                {formatVisibilityLabel(document.supplemental.visibilityScope)}
                            </Badge>
                        </div>

                        <div className="space-y-1">
                            <h2 className="text-xl font-semibold text-gray-950 dark:text-white">{document.title}</h2>
                            <p className="text-sm text-gray-500">
                                Đơn vị ban hành {document.supplemental.issuingUnit} • cập nhật {formatDateTime(document.updatedAt)}
                            </p>
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-3">
                        {isAdminViewer ? (
                            <>
                                <Button asChild variant="outline">
                                    <Link to={`/admin/audit-logs?targetType=document&search=${encodeURIComponent(document.id)}`}>
                                        Nhật ký liên quan
                                    </Link>
                                </Button>
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={handleReindex}
                                    isLoading={reindexMutation.isPending}
                                >
                                    Lập chỉ mục lại
                                </Button>
                                <Button
                                    type="button"
                                    variant="danger"
                                    onClick={handleArchive}
                                    isLoading={archiveMutation.isPending}
                                    disabled={document.system.isArchived}
                                >
                                    Lưu trữ
                                </Button>
                            </>
                        ) : null}

                        <Button asChild variant="secondary">
                            <Link to="/chat">Quay lại chat</Link>
                        </Button>
                    </div>
                </div>

                <div className="rounded-2xl border border-brand-200 bg-brand-50/80 p-4 dark:border-brand-900 dark:bg-brand-950/30">
                    <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                        <ShieldCheck size={16} />
                        {trustSummary.title}
                    </div>
                    <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{trustSummary.description}</p>
                </div>
            </Card>

            <div className="grid gap-6 xl:grid-cols-2">
                <MetadataPanel
                    title="Thông tin chính"
                    entries={[
                        { label: 'Loại tài liệu', value: formatDocumentType(document.temporal.documentType) },
                        { label: 'Độ tin cậy', value: formatPercent(document.temporal.confidence) },
                        { label: 'Hiệu lực từ', value: formatOptionalDate(document.temporal.validFrom) },
                        { label: 'Hiệu lực đến', value: formatOptionalDate(document.temporal.validUntil) },
                        { label: 'Năm học', value: formatOptionalText(document.temporal.academicYear, 'Chưa xác định') },
                        {
                            label: 'Khóa áp dụng',
                            value: document.temporal.cohortYears.length > 0 ? document.temporal.cohortYears.join(', ') : 'Chưa xác định',
                        },
                        { label: 'Số hiệu', value: formatOptionalText(document.temporal.documentNumber, 'Chưa cập nhật') },
                    ]}
                />

                <MetadataPanel
                    title="Nguồn trích dẫn"
                    entries={[
                        { label: 'Đơn vị ban hành', value: document.supplemental.issuingUnit },
                        { label: 'Phạm vi sử dụng', value: formatVisibilityLabel(document.supplemental.visibilityScope) },
                        { label: 'Lập chỉ mục lúc', value: formatOptionalDateTime(document.system.indexedAt) },
                        { label: 'Ghi chú', value: formatOptionalText(document.supplemental.notes, 'Không có ghi chú bổ sung') },
                        {
                            label: 'Tài liệu liên quan',
                            value: document.temporal.amendsDocuments.length > 0 ? document.temporal.amendsDocuments.join(', ') : 'Không có',
                        },
                    ]}
                />
            </div>

            <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <Card className="space-y-4">
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">Điểm cần lưu ý</div>
                    <div className="space-y-3">
                        {(currentVersion?.changeHighlights ?? []).length > 0 ? (
                            currentVersion?.changeHighlights.map((highlight) => (
                                <div
                                    key={highlight}
                                    className="rounded-2xl border border-brand-200 bg-white/90 px-4 py-3 text-sm text-gray-700 shadow-theme-xs dark:border-brand-900 dark:bg-gray-900/70 dark:text-gray-100"
                                >
                                    {highlight}
                                </div>
                            ))
                        ) : (
                            <p className="text-sm text-gray-500">Tài liệu này chưa có ghi chú thay đổi nổi bật.</p>
                        )}
                    </div>
                </Card>

                <Card className="space-y-4">
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">Hướng dẫn sử dụng</div>
                    <div className="space-y-3 text-sm text-gray-600 dark:text-gray-300">
                        <p>
                            Tài liệu công khai nên được dùng cùng trích dẫn, thời gian hiệu lực và ngữ cảnh áp dụng để tránh trả lời quá mức.
                        </p>
                        <p>
                            Với tài liệu chờ rà soát hoặc đã lưu trữ, giao diện cần hiển thị cảnh báo rõ ràng thay vì trình bày như quy định cuối cùng.
                        </p>
                        <p>
                            Khi có mâu thuẫn giữa nhiều nguồn, ưu tiên văn bản mới hơn và kiểm tra lại đơn vị ban hành trước khi kết luận.
                        </p>
                    </div>
                </Card>
            </div>

            {isAdminViewer ? (
                <MetadataPanel
                    title="Thông tin nội bộ dành cho quản trị"
                    entries={[
                        { label: 'Người sở hữu', value: document.ownerName },
                        { label: 'Email nội bộ', value: document.ownerEmail },
                        { label: 'Nguồn hệ thống', value: document.system.fileSource },
                        { label: 'Mã băm nội dung', value: document.system.contentHash },
                        { label: 'Phiên bản', value: document.system.versionNumber },
                        { label: 'Review ID', value: formatOptionalText(document.traceability?.sourceReviewId, 'Không liên kết') },
                        { label: 'Submission ID', value: formatOptionalText(document.traceability?.sourceSubmissionId, 'Không liên kết') },
                        { label: 'Xuất bản lúc', value: formatOptionalDateTime(document.traceability?.publishedAt) },
                    ]}
                />
            ) : null}
        </div>
    )
}
