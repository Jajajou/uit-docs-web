import { Link } from 'react-router-dom'
import { ArrowRight, CalendarDays, FileSearch, History, Layers3, ShieldCheck, Sparkles, Users } from 'lucide-react'
import { toast } from 'sonner'
import { useSessionQuery } from '@/entities/auth/queries'
import { getLifecycleTone, getProcessingTone, getVisibilityTone } from '@/entities/documents/presentation'
import { useArchiveDocumentMutation, useDocumentDetailQuery, useReindexDocumentMutation } from '@/entities/documents/queries'
import type { Document, DocumentLifecycleStatus, DocumentVersionEntry, VisibilityScope } from '@/entities/documents/types'
import { formatDate, formatDateTime, formatPercent } from '@/shared/lib/format'
import { Badge, BrandLoadingAnimation, Button, Card, EmptyState, MetadataPanel } from '@/shared/ui'

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

function getValiditySummary(document: Document) {
    const now = Date.now()
    const validFrom = document.temporal.validFrom ? new Date(document.temporal.validFrom).getTime() : null
    const validUntil = document.temporal.validUntil ? new Date(document.temporal.validUntil).getTime() : null

    if (validUntil && validUntil < now) {
        return {
            tone: 'warning' as const,
            label: 'Đã hết hiệu lực',
            description: `Hết hiệu lực từ ${formatDate(document.temporal.validUntil ?? '')}.`,
        }
    }

    if (validFrom && validFrom > now) {
        return {
            tone: 'brand' as const,
            label: 'Sắp có hiệu lực',
            description: `Bắt đầu áp dụng từ ${formatDate(document.temporal.validFrom ?? '')}.`,
        }
    }

    if (validFrom || validUntil) {
        const rangeLabel =
            validFrom && validUntil
                ? `Áp dụng từ ${formatDate(document.temporal.validFrom ?? '')} đến ${formatDate(document.temporal.validUntil ?? '')}.`
                : validFrom
                  ? `Đang áp dụng từ ${formatDate(document.temporal.validFrom ?? '')}.`
                  : `Chưa có ngày bắt đầu, hiện ghi nhận tới ${formatDate(document.temporal.validUntil ?? '')}.`

        return {
            tone: 'success' as const,
            label: 'Đang trong hiệu lực',
            description: rangeLabel,
        }
    }

    return {
        tone: 'neutral' as const,
        label: 'Chưa có mốc hiệu lực',
        description: 'Chưa có mốc thời gian rõ ràng, cần đọc cùng đơn vị ban hành và ngữ cảnh áp dụng.',
    }
}

function getAudienceSummary(document: Document) {
    const cohortLabel = document.temporal.cohortYears.length > 0 ? document.temporal.cohortYears.join(', ') : 'Chưa khóa cụ thể'
    const academicYear = formatOptionalText(document.temporal.academicYear, 'Chưa chốt năm học')

    return {
        label: academicYear,
        description: `Khóa áp dụng: ${cohortLabel}. Phạm vi: ${formatVisibilityLabel(document.supplemental.visibilityScope)}.`,
    }
}

function getVersionSummary(document: Document, currentVersion?: DocumentVersionEntry) {
    return {
        label: `v${document.system.versionNumber}`,
        description: currentVersion
            ? `Cập nhật gần nhất ${formatDateTime(currentVersion.createdAt)} bởi ${currentVersion.createdByName}.`
            : `Lập chỉ mục lúc ${formatDateTime(document.system.indexedAt)}.`,
    }
}

function getTraceabilitySummary(document: Document) {
    if (document.traceability?.publishedAt) {
        return {
            tone: 'success' as const,
            label: 'Có dấu vết phát hành',
            description: `Xuất bản ${formatDateTime(document.traceability.publishedAt)}${document.traceability.reviewedByName ? ` bởi ${document.traceability.reviewedByName}` : ''}.`,
        }
    }

    if (document.traceability?.sourceReviewId || document.traceability?.sourceSubmissionId) {
        return {
            tone: 'brand' as const,
            label: 'Có traceability nội bộ',
            description: 'Đã liên kết sang luồng review hoặc submission, nhưng chưa có mốc xuất bản cuối cùng.',
        }
    }

    return {
        tone: 'neutral' as const,
        label: 'Chưa đủ traceability',
        description: 'Chưa có mối nối phát hành rõ ràng, nên đọc cùng trạng thái duyệt và nguồn hệ thống.',
    }
}

function formatAuditActionLabel(action: string) {
    switch (action) {
        case 'upload_submission':
            return 'Nộp tài liệu'
        case 'approve_review':
            return 'Duyệt review'
        case 'reject_review':
            return 'Từ chối review'
        case 'request_changes':
            return 'Yêu cầu chỉnh sửa'
        case 'archive_document':
            return 'Lưu trữ tài liệu'
        case 'reindex_document':
            return 'Lập chỉ mục lại'
        case 'login':
            return 'Đăng nhập'
        case 'role_switch':
            return 'Chuyển vai trò'
        default:
            return action
    }
}

export function DocumentDetailPanel({ id, scenario }: { id: string; scenario?: string }) {
    const documentQuery = useDocumentDetailQuery(id, { scenario })
    const sessionQuery = useSessionQuery({ scenario })
    const archiveMutation = useArchiveDocumentMutation({ scenario })
    const reindexMutation = useReindexDocumentMutation({ scenario })

    if (documentQuery.isLoading) {
        return (
            <Card className="flex min-h-[26rem] items-center justify-center border-white/70 bg-white/92 p-8 shadow-theme-lg backdrop-blur-sm dark:border-white/8 dark:bg-[#0f1728]/90">
                <BrandLoadingAnimation
                    title="Đang đối chiếu tài liệu"
                    description="UIT AI đang tải metadata, nguồn trích dẫn và trạng thái hiệu lực của tài liệu này."
                    size={220}
                />
            </Card>
        )
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
    const validitySummary = getValiditySummary(document)
    const audienceSummary = getAudienceSummary(document)
    const versionSummary = getVersionSummary(document, currentVersion)
    const traceabilitySummary = getTraceabilitySummary(document)
    const recentVersionHistory = document.versionHistory.slice(0, 4)
    const recentActivity = document.activityHistory.slice(0, 4)
    const tags = document.supplemental.tags
    const relatedDocuments = document.temporal.amendsDocuments

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

    const quickSummaryCards = [
        {
            title: 'Hiệu lực',
            value: validitySummary.label,
            description: validitySummary.description,
            tone: validitySummary.tone,
            icon: CalendarDays,
        },
        {
            title: 'Đối tượng áp dụng',
            value: audienceSummary.label,
            description: audienceSummary.description,
            tone: 'brand' as const,
            icon: Users,
        },
        {
            title: 'Phiên bản hiện hành',
            value: versionSummary.label,
            description: versionSummary.description,
            tone: 'neutral' as const,
            icon: Layers3,
        },
        {
            title: 'Dấu vết phát hành',
            value: traceabilitySummary.label,
            description: traceabilitySummary.description,
            tone: traceabilitySummary.tone,
            icon: History,
        },
    ]

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
                                <Button type="button" variant="outline" onClick={handleReindex} isLoading={reindexMutation.isPending}>
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
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                            <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                                <ShieldCheck size={16} />
                                {trustSummary.title}
                            </div>
                            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{trustSummary.description}</p>
                        </div>

                        <div className="flex flex-wrap gap-2">
                            <Button asChild variant="outline" size="sm">
                                <Link to="/documents">
                                    Về thư viện
                                    <ArrowRight size={14} />
                                </Link>
                            </Button>
                            <Button asChild size="sm">
                                <Link to="/chat">
                                    Hỏi UIT AI
                                    <Sparkles size={14} />
                                </Link>
                            </Button>
                        </div>
                    </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    {quickSummaryCards.map((item) => {
                        const Icon = item.icon

                        return (
                            <div
                                key={item.title}
                                className="rounded-[1.6rem] border border-white/75 bg-white/88 p-4 shadow-theme-xs dark:border-white/10 dark:bg-[#111c2f]/86"
                            >
                                <div className="flex items-start justify-between gap-3">
                                    <div className="space-y-1">
                                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-400">{item.title}</div>
                                        <div className="text-base font-semibold text-gray-950 dark:text-white">{item.value}</div>
                                    </div>
                                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-brand-100 bg-brand-50 text-brand-600 dark:border-brand-900 dark:bg-brand-950/40 dark:text-brand-200">
                                        <Icon size={18} />
                                    </div>
                                </div>

                                <div className="mt-3">
                                    <Badge tone={item.tone}>{item.value}</Badge>
                                    <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{item.description}</p>
                                </div>
                            </div>
                        )
                    })}
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
                            value: relatedDocuments.length > 0 ? relatedDocuments.join(', ') : 'Không có',
                        },
                    ]}
                />
            </div>

            <div className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
                <Card className="space-y-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">Điểm cần lưu ý</div>
                        {tags.length > 0 ? <Badge tone="neutral">{`${tags.length} tag`}</Badge> : null}
                    </div>

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

                    {tags.length > 0 ? (
                        <div className="space-y-3">
                            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-400">Tag nội dung</div>
                            <div className="flex flex-wrap gap-2">
                                {tags.map((tag) => (
                                    <Badge key={tag} tone="neutral">
                                        {tag}
                                    </Badge>
                                ))}
                            </div>
                        </div>
                    ) : null}

                    {relatedDocuments.length > 0 ? (
                        <div className="space-y-3">
                            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-400">Tài liệu liên quan</div>
                            <div className="flex flex-wrap gap-2">
                                {relatedDocuments.map((relatedDocument) => (
                                    <Badge key={relatedDocument} tone="brand">
                                        {relatedDocument}
                                    </Badge>
                                ))}
                            </div>
                        </div>
                    ) : null}

                    <div className="rounded-[1.6rem] border border-white/80 bg-white/92 p-4 dark:border-white/10 dark:bg-[#111c2f]/86">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">Cách dùng trong chat</div>
                        <ul className="mt-3 space-y-2 text-sm leading-6 text-gray-600 dark:text-gray-300">
                            <li>Tài liệu công khai nên được dùng cùng trích dẫn, thời gian hiệu lực và ngữ cảnh áp dụng để tránh trả lời quá mức.</li>
                            <li>Với tài liệu chờ rà soát hoặc đã lưu trữ, giao diện cần hiển thị cảnh báo rõ ràng thay vì trình bày như quy định cuối cùng.</li>
                            <li>Khi có mâu thuẫn giữa nhiều nguồn, ưu tiên văn bản mới hơn và kiểm tra lại đơn vị ban hành trước khi kết luận.</li>
                        </ul>
                    </div>
                </Card>

                <Card className="space-y-5">
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">Phiên bản và dấu vết</div>

                    <div className="rounded-[1.6rem] border border-brand-200 bg-brand-50/75 p-4 dark:border-brand-900 dark:bg-brand-950/30">
                        <div className="flex flex-wrap items-center gap-2">
                            <Badge tone="brand">{versionSummary.label}</Badge>
                            {currentVersion?.isCurrent ? <Badge tone="success">Bản hiện hành</Badge> : null}
                        </div>
                        <div className="mt-3 space-y-1">
                            <div className="text-sm font-semibold text-gray-900 dark:text-white">
                                {currentVersion?.changeSummary || 'Chưa có ghi chú phiên bản mới nhất'}
                            </div>
                            <p className="text-sm leading-6 text-gray-600 dark:text-gray-300">{versionSummary.description}</p>
                        </div>
                    </div>

                    <div className="space-y-3">
                        {recentVersionHistory.length > 0 ? (
                            recentVersionHistory.map((versionEntry) => (
                                <div
                                    key={versionEntry.id}
                                    className="rounded-[1.4rem] border border-white/75 bg-white/90 p-4 shadow-theme-xs dark:border-white/10 dark:bg-[#111c2f]/86"
                                >
                                    <div className="flex flex-wrap items-center justify-between gap-3">
                                        <div>
                                            <div className="text-sm font-semibold text-gray-950 dark:text-white">
                                                {`v${versionEntry.versionNumber} • ${versionEntry.createdByName}`}
                                            </div>
                                            <div className="text-xs text-gray-500">{formatDateTime(versionEntry.createdAt)}</div>
                                        </div>
                                        {versionEntry.isCurrent ? <Badge tone="success">Hiện hành</Badge> : <Badge tone="neutral">Lịch sử</Badge>}
                                    </div>

                                    <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{versionEntry.changeSummary}</p>
                                </div>
                            ))
                        ) : (
                            <p className="text-sm text-gray-500">Chưa có lịch sử phiên bản để hiển thị.</p>
                        )}
                    </div>

                    {recentActivity.length > 0 ? (
                        <div className="space-y-3 border-t border-white/70 pt-4 dark:border-white/10">
                            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-400">Hoạt động gần đây</div>
                            <div className="space-y-3">
                                {recentActivity.map((activityEntry) => (
                                    <div key={activityEntry.id} className="flex items-start gap-3">
                                        <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-brand-100 bg-brand-50 text-brand-600 dark:border-brand-900 dark:bg-brand-950/40 dark:text-brand-200">
                                            <History size={16} />
                                        </div>
                                        <div className="min-w-0">
                                            <div className="text-sm font-semibold text-gray-900 dark:text-white">
                                                {formatAuditActionLabel(activityEntry.action)}
                                            </div>
                                            <div className="text-sm leading-6 text-gray-600 dark:text-gray-300">
                                                {activityEntry.actorName} • {formatDateTime(activityEntry.createdAt)}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : null}
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
