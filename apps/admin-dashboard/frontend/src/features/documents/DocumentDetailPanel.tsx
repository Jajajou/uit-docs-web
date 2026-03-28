import { Link } from 'react-router-dom'
import { BookOpenText, FileSearch, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { formatAuditAction, getAuditTargetPath } from '@/entities/admin/presentation'
import { useSessionQuery } from '@/entities/auth/queries'
import { getDocumentTrustState, getLifecycleTone, getProcessingTone, getVisibilityTone, formatStatusLabel } from '@/entities/documents/presentation'
import { useArchiveDocumentMutation, useDocumentDetailQuery, useReindexDocumentMutation } from '@/entities/documents/queries'
import { formatDate, formatDateTime, formatPercent } from '@/shared/lib/format'
import { Badge, Button, Card, EmptyState, MetadataPanel } from '@/shared/ui'

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
                title="Document not found"
                description="This foundational detail page could not find the requested document."
            />
        )
    }

    const document = documentQuery.data
    const trustState = getDocumentTrustState(document)
    const canManageDocument = sessionQuery.data ? ['operator', 'admin'].includes(sessionQuery.data.user.role) : false
    const canInspectAudit = sessionQuery.data?.user.role === 'admin'
    const isAdminBreakGlass = sessionQuery.data?.user.role === 'admin'
    const currentVersion = document.versionHistory.find((entry) => entry.isCurrent) ?? document.versionHistory[0]

    const handleArchive = async () => {
        try {
            const updatedDocument = await archiveMutation.mutateAsync(document.id)
            toast.success(`Archived ${updatedDocument.title}`, {
                description: isAdminBreakGlass
                    ? 'The document is now historical reference and the admin support override was recorded in audit logs.'
                    : 'The document is now marked as historical reference and audit logs were updated.',
            })
        } catch (error) {
            toast.error('Archive failed', {
                description: error instanceof Error ? error.message : 'Unable to archive this document.',
            })
        }
    }

    const handleReindex = async () => {
        try {
            const updatedDocument = await reindexMutation.mutateAsync(document.id)
            toast.success(`Reindex started for ${updatedDocument.title}`, {
                description: isAdminBreakGlass
                    ? 'Processing moved to indexing and the admin support override was recorded in audit logs.'
                    : 'Processing status moved to indexing and a job entry was queued.',
            })
        } catch (error) {
            toast.error('Reindex failed', {
                description: error instanceof Error ? error.message : 'Unable to reindex this document.',
            })
        }
    }

    return (
        <div className="space-y-6">
            <Card className="space-y-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-2">
                        <div className="flex flex-wrap gap-2">
                            <Badge tone={trustState.tone}>{trustState.title}</Badge>
                            <Badge tone={getLifecycleTone(document.lifecycleStatus)}>{formatStatusLabel(document.lifecycleStatus)}</Badge>
                            <Badge tone={getProcessingTone(document.processingStatus)}>{formatStatusLabel(document.processingStatus)}</Badge>
                            <Badge tone={getVisibilityTone(document.supplemental.visibilityScope)}>{document.supplemental.visibilityScope}</Badge>
                        </div>
                        <div>
                            <h2 className="text-xl font-semibold text-gray-950 dark:text-white">{document.title}</h2>
                            <p className="mt-1 text-sm text-gray-500">
                                Owner {document.ownerName} ({document.ownerEmail}) - indexed {formatDateTime(document.system.indexedAt)}.
                            </p>
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-3">
                        {canInspectAudit ? (
                            <Button asChild variant="outline">
                                <Link to={`/admin/audit-logs?targetType=document&search=${encodeURIComponent(document.id)}`}>Open audit trail</Link>
                            </Button>
                        ) : null}
                        {canManageDocument ? (
                            <>
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={handleReindex}
                                    isLoading={reindexMutation.isPending}
                                >
                                    {isAdminBreakGlass ? 'Reindex document (support override)' : 'Reindex document'}
                                </Button>
                                <Button
                                    type="button"
                                    variant="danger"
                                    onClick={handleArchive}
                                    isLoading={archiveMutation.isPending}
                                    disabled={document.system.isArchived}
                                >
                                    {isAdminBreakGlass ? 'Archive document (support override)' : 'Archive document'}
                                </Button>
                            </>
                        ) : null}
                        <Button asChild variant="secondary">
                            <Link to="/chat">Open public chat</Link>
                        </Button>
                    </div>
                </div>

                <div
                    className={`rounded-2xl border p-4 ${
                        trustState.tone === 'success'
                            ? 'border-success-200 bg-success-50 dark:border-success-800 dark:bg-success-950'
                            : trustState.tone === 'warning'
                              ? 'border-warning-200 bg-warning-50 dark:border-warning-800 dark:bg-warning-950'
                              : trustState.tone === 'danger'
                                ? 'border-error-200 bg-error-50 dark:border-error-800 dark:bg-error-950'
                                : 'border-brand-200 bg-brand-50 dark:border-brand-900 dark:bg-brand-950'
                    }`}
                >
                    <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                        <ShieldCheck size={16} />
                        Citation trust summary
                    </div>
                    <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{trustState.description}</p>
                    {canManageDocument ? (
                        <p className="mt-3 text-xs text-gray-500">
                            Operator actions are available here for archive and reindex flows, and each action should appear in admin audit logs.
                        </p>
                    ) : null}
                </div>

                {isAdminBreakGlass ? (
                    <div className="rounded-2xl border border-warning-200 bg-warning-50 p-4 text-sm text-warning-900 dark:border-warning-800 dark:bg-warning-950 dark:text-warning-100">
                        <div className="font-semibold">Break-glass support mode</div>
                        <p className="mt-2">
                            You are acting as `admin` on operator-owned document controls. Archive and reindex stay available for support incidents only, and every action remains explicitly auditable.
                        </p>
                    </div>
                ) : null}
            </Card>

            <div className="grid gap-6 xl:grid-cols-2">
                <MetadataPanel
                    title="Temporal metadata"
                    entries={[
                        { label: 'Document type', value: document.temporal.documentType },
                        { label: 'Confidence', value: formatPercent(document.temporal.confidence) },
                        { label: 'Valid from', value: formatDate(document.temporal.validFrom) },
                        { label: 'Valid until', value: formatDate(document.temporal.validUntil) },
                        { label: 'Academic year', value: document.temporal.academicYear },
                        { label: 'Cohort years', value: document.temporal.cohortYears.join(', ') || 'Not detected' },
                        { label: 'Document number', value: document.temporal.documentNumber },
                        { label: 'Reasoning', value: document.temporal.reasoning || 'No extraction reasoning recorded' },
                    ]}
                />
                <MetadataPanel
                    title="System provenance"
                    entries={[
                        { label: 'File source', value: document.system.fileSource },
                        { label: 'Indexed at', value: formatDateTime(document.system.indexedAt) },
                        { label: 'Content hash', value: document.system.contentHash },
                        { label: 'Version', value: document.system.versionNumber },
                        { label: 'Archived', value: document.system.isArchived ? 'Yes' : 'No' },
                    ]}
                />
            </div>

            <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <Card className="space-y-4">
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">Traceability chain</div>
                    <div className="space-y-3 text-sm text-gray-600 dark:text-gray-300">
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Source submission:</span>{' '}
                            {document.traceability?.sourceSubmissionId ? (
                                <Link className="text-brand-700 hover:text-brand-800 dark:text-brand-300" to={`/portal/submissions/${document.traceability.sourceSubmissionId}`}>
                                    {document.traceability.sourceSubmissionId}
                                </Link>
                            ) : (
                                'Legacy or external document'
                            )}
                        </div>
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Review decision:</span>{' '}
                            {document.traceability?.sourceReviewId ? (
                                <Link className="text-brand-700 hover:text-brand-800 dark:text-brand-300" to="/portal/review">
                                    {document.traceability.sourceReviewId}
                                </Link>
                            ) : (
                                'Not linked'
                            )}
                        </div>
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Reviewed by:</span>{' '}
                            {document.traceability?.reviewedByName ?? 'Not recorded'}
                        </div>
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Published at:</span>{' '}
                            {formatDateTime(document.traceability?.publishedAt)}
                        </div>
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Publication reason:</span>{' '}
                            {document.traceability?.publicationReason ?? 'No publication rationale recorded'}
                        </div>
                    </div>
                </Card>

                <Card className="space-y-4">
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">Current version change highlights</div>
                    <div className="space-y-3">
                        {currentVersion?.changeHighlights?.length ? (
                            currentVersion.changeHighlights.map((highlight) => (
                                <div key={highlight} className="rounded-2xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-900 dark:border-brand-900 dark:bg-brand-950 dark:text-brand-100">
                                    {highlight}
                                </div>
                            ))
                        ) : (
                            <p className="text-sm text-gray-500">No metadata diff summary has been recorded for the current version yet.</p>
                        )}
                    </div>
                    {currentVersion?.sourceSubmissionId || currentVersion?.sourceReviewId ? (
                        <div className="flex flex-wrap gap-2">
                            {currentVersion.sourceSubmissionId ? <Badge tone="brand">Submission {currentVersion.sourceSubmissionId}</Badge> : null}
                            {currentVersion.sourceReviewId ? <Badge tone="neutral">Review {currentVersion.sourceReviewId}</Badge> : null}
                        </div>
                    ) : null}
                </Card>
            </div>

            <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <Card className="space-y-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                        <BookOpenText size={16} />
                        Supplemental context
                    </div>
                    <div className="space-y-3 text-sm text-gray-600 dark:text-gray-300">
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Issuing unit:</span> {document.supplemental.issuingUnit}
                        </div>
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Tags:</span>{' '}
                            {document.supplemental.tags.length > 0 ? document.supplemental.tags.join(', ') : 'No tags'}
                        </div>
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Visibility:</span> {document.supplemental.visibilityScope}
                        </div>
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Notes:</span> {document.supplemental.notes}
                        </div>
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Amends documents:</span>{' '}
                            {document.temporal.amendsDocuments.length > 0 ? document.temporal.amendsDocuments.join(', ') : 'None'}
                        </div>
                    </div>
                </Card>

                <Card className="space-y-4">
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">Public assistant policy</div>
                    <div className="space-y-3 text-sm text-gray-500">
                        <p>
                            Approved and public documents can be cited in student-facing chat, but the answer should still show references and confidence cues.
                        </p>
                        <p>
                            Pending, rejected or archived documents should either be blocked from trusted answers or shown with explicit warnings.
                        </p>
                        <p>
                            Internal-only documents can support staff workflows, but they should not silently appear as public student guidance.
                        </p>
                    </div>
                </Card>
            </div>

            <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <Card className="space-y-4">
                    <div className="flex items-center justify-between gap-3">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">Version history</div>
                        <Badge tone="brand">v{document.system.versionNumber}</Badge>
                    </div>
                    <div className="space-y-3">
                        {document.versionHistory.length > 0 ? (
                            document.versionHistory.map((entry) => (
                                <div key={entry.id} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <div className="text-sm font-semibold text-gray-900 dark:text-white">Version {entry.versionNumber}</div>
                                                {entry.isCurrent ? <Badge tone="success">Current</Badge> : <Badge tone="neutral">Previous</Badge>}
                                            </div>
                                            <p className="mt-1 text-sm text-gray-500">{entry.changeSummary}</p>
                                        </div>
                                        <div className="text-xs text-gray-500">{formatDateTime(entry.createdAt)}</div>
                                    </div>
                                    <div className="mt-3 grid gap-2 text-xs text-gray-500">
                                        <div>
                                            <span className="font-semibold text-gray-900 dark:text-white">Updated by:</span> {entry.createdByName}
                                        </div>
                                        <div>
                                            <span className="font-semibold text-gray-900 dark:text-white">Traceability:</span>{' '}
                                            {entry.sourceSubmissionId ? (
                                                <Link className="text-brand-700 hover:text-brand-800 dark:text-brand-300" to={`/portal/submissions/${entry.sourceSubmissionId}`}>
                                                    {entry.sourceSubmissionId}
                                                </Link>
                                            ) : (
                                                'Legacy source'
                                            )}
                                            {entry.sourceReviewId ? (
                                                <>
                                                    {' '}via{' '}
                                                    <Link className="text-brand-700 hover:text-brand-800 dark:text-brand-300" to="/portal/review">
                                                        {entry.sourceReviewId}
                                                    </Link>
                                                </>
                                            ) : null}
                                        </div>
                                        <div>
                                            <span className="font-semibold text-gray-900 dark:text-white">Source:</span> {entry.fileSource}
                                        </div>
                                        <div>
                                            <span className="font-semibold text-gray-900 dark:text-white">Hash:</span> {entry.contentHash}
                                        </div>
                                    </div>
                                    {entry.changeHighlights.length > 0 ? (
                                        <div className="mt-3 flex flex-wrap gap-2">
                                            {entry.changeHighlights.map((highlight) => (
                                                <Badge key={`${entry.id}-${highlight}`} tone="brand">
                                                    {highlight}
                                                </Badge>
                                            ))}
                                        </div>
                                    ) : null}
                                </div>
                            ))
                        ) : (
                            <p className="text-sm text-gray-500">No version snapshots have been recorded for this document yet.</p>
                        )}
                    </div>
                </Card>

                <Card className="space-y-4">
                    <div className="flex items-center justify-between gap-3">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">Related activity</div>
                        {canInspectAudit ? (
                            <Button asChild variant="ghost" size="sm">
                                <Link to={`/admin/audit-logs?targetType=document&search=${encodeURIComponent(document.id)}`}>Filtered audit logs</Link>
                            </Button>
                        ) : null}
                    </div>
                    <div className="space-y-3">
                        {document.activityHistory.length > 0 ? (
                            document.activityHistory.map((entry) => {
                                const targetPath = getAuditTargetPath(entry)

                                return (
                                    <div key={entry.id} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
                                        <div className="flex flex-wrap items-start justify-between gap-3">
                                            <div className="space-y-1">
                                                <Badge tone="brand">{formatAuditAction(entry.action)}</Badge>
                                                <div className="text-sm text-gray-600 dark:text-gray-300">
                                                    {entry.actorName} ({entry.actorRole}) on {formatDateTime(entry.createdAt)}
                                                </div>
                                            </div>
                                            <div className="text-xs text-gray-500">{entry.targetType}</div>
                                        </div>
                                        <div className="mt-3 text-sm text-gray-600 dark:text-gray-300">
                                            {targetPath ? (
                                                <Link to={targetPath} className="font-medium text-gray-900 hover:text-brand-700 dark:text-white">
                                                    {entry.targetLabel}
                                                </Link>
                                            ) : (
                                                <span className="font-medium text-gray-900 dark:text-white">{entry.targetLabel}</span>
                                            )}{' '}
                                            ({entry.targetId})
                                        </div>
                                    </div>
                                )
                            })
                        ) : (
                            <p className="text-sm text-gray-500">No related activity has been captured for this document yet.</p>
                        )}
                    </div>
                </Card>
            </div>
        </div>
    )
}
