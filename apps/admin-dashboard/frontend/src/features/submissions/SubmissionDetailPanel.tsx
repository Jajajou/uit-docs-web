import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { FileStack, GitPullRequest, Sparkles } from 'lucide-react'
import { getLifecycleTone, getProcessingTone, getVisibilityTone, formatStatusLabel } from '@/entities/documents/presentation'
import { useDocumentDetailQuery } from '@/entities/documents/queries'
import { useReviewTasksQuery } from '@/entities/reviews/queries'
import { useSubmissionDetailQuery } from '@/entities/submissions/queries'
import type { ReviewTask } from '@/entities/reviews/types'
import { formatDateTime, formatPercent } from '@/shared/lib/format'
import { Badge, Button, Card, EmptyState, MetadataPanel, StatusTimeline } from '@/shared/ui'

function getTimelineState(step: 'done' | 'current' | 'pending' | 'failed' | undefined) {
    return step ?? 'pending'
}

function getMetadataDiffSummary(task?: ReviewTask) {
    if (!task) {
        return []
    }

    const rows = [
        ['Document type', task.extractedTemporal.documentType, task.editedTemporal.documentType],
        ['Valid from', task.extractedTemporal.validFrom ?? 'Not detected', task.editedTemporal.validFrom ?? 'Not confirmed'],
        ['Valid until', task.extractedTemporal.validUntil ?? 'Not detected', task.editedTemporal.validUntil ?? 'Not confirmed'],
        ['Academic year', task.extractedTemporal.academicYear ?? 'Not detected', task.editedTemporal.academicYear ?? 'Not confirmed'],
        [
            'Cohort years',
            task.extractedTemporal.cohortYears.join(', ') || 'Not detected',
            task.editedTemporal.cohortYears.join(', ') || 'Not confirmed',
        ],
        ['Document number', task.extractedTemporal.documentNumber ?? 'Not detected', task.editedTemporal.documentNumber ?? 'Not confirmed'],
    ]

    return rows
        .filter(([, extracted, edited]) => extracted !== edited)
        .map(([label, extracted, edited]) => ({ label, extracted, edited }))
}

export function SubmissionDetailPanel({ id, scenario }: { id: string; scenario?: string }) {
    const submissionQuery = useSubmissionDetailQuery(id, { scenario })
    const reviewTasksQuery = useReviewTasksQuery({ scenario })
    const linkedDocumentQuery = useDocumentDetailQuery(submissionQuery.data?.linkedDocumentId ?? '', {
        scenario,
    })

    const relatedReviewTask = useMemo(() => {
        if (!submissionQuery.data || !reviewTasksQuery.data) {
            return undefined
        }

        const matches = reviewTasksQuery.data.filter((task) => task.submissionId === submissionQuery.data?.id)

        return matches.sort((left, right) => {
            if (left.status === 'pending_review' && right.status !== 'pending_review') {
                return -1
            }

            if (right.status === 'pending_review' && left.status !== 'pending_review') {
                return 1
            }

            return right.createdAt.localeCompare(left.createdAt)
        })[0]
    }, [reviewTasksQuery.data, submissionQuery.data])

    if (submissionQuery.isLoading) {
        return <Card className="h-80 animate-pulse" />
    }

    if (submissionQuery.isError) {
        return <Card className="text-sm text-error-700 dark:text-error-300">{submissionQuery.error.message}</Card>
    }

    if (!submissionQuery.data) {
        return (
            <EmptyState
                icon={FileStack}
                title="Submission not found"
                description="The selected submission could not be loaded from the current mock scenario."
            />
        )
    }

    const submission = submissionQuery.data
    const diffSummary = getMetadataDiffSummary(relatedReviewTask)
    const linkedDocument = submission.linkedDocumentId ? linkedDocumentQuery.data : null
    const currentVersion = linkedDocument?.versionHistory.find((entry) => entry.isCurrent) ?? linkedDocument?.versionHistory[0]

    const timelineSteps = [
        {
            id: 'uploaded',
            label: 'Submission received',
            description: `Uploaded ${formatDateTime(submission.createdAt)} via ${submission.sourceType}.`,
            state: 'done' as const,
        },
        {
            id: 'extraction',
            label: 'Extraction pipeline',
            description: `${submission.temporal.documentType} detected with ${formatPercent(submission.temporal.confidence)} confidence.`,
            state:
                submission.processingStatus === 'failed'
                    ? ('failed' as const)
                    : submission.processingStatus === 'completed'
                      ? ('done' as const)
                      : ('current' as const),
        },
        {
            id: 'review',
            label: 'Reviewer decision',
            description: relatedReviewTask
                ? `${relatedReviewTask.reviewerName} marked this as ${formatStatusLabel(relatedReviewTask.status)}.`
                                : 'Waiting for admin review and metadata confirmation.',
            state:
                submission.lifecycleStatus === 'approved'
                    ? ('done' as const)
                    : submission.lifecycleStatus === 'rejected'
                      ? ('failed' as const)
                      : submission.lifecycleStatus === 'pending_review'
                        ? ('current' as const)
                        : ('pending' as const),
        },
        {
            id: 'public-release',
            label: 'Public release',
            description: submission.linkedDocumentId
                ? `Published as document ${submission.linkedDocumentId} and ready for downstream routes.`
                : submission.supplemental.visibilityScope === 'public'
                  ? 'Will become available to public chat after approval and publication.'
                  : 'Will remain internal after approval.',
            state:
                submission.linkedDocumentId
                    ? ('done' as const)
                    : submission.lifecycleStatus === 'rejected'
                      ? ('failed' as const)
                      : getTimelineState(undefined),
        },
    ]

    return (
        <div className="space-y-6">
            <Card className="space-y-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-2">
                        <div className="flex flex-wrap gap-2">
                            <Badge tone={getLifecycleTone(submission.lifecycleStatus)}>{formatStatusLabel(submission.lifecycleStatus)}</Badge>
                            <Badge tone={getProcessingTone(submission.processingStatus)}>{formatStatusLabel(submission.processingStatus)}</Badge>
                            <Badge tone={getVisibilityTone(submission.supplemental.visibilityScope)}>{submission.supplemental.visibilityScope}</Badge>
                            <Badge tone="neutral">{submission.sourceType}</Badge>
                        </div>
                        <div>
                            <h2 className="text-xl font-semibold text-gray-950 dark:text-white">{submission.title}</h2>
                            <p className="mt-1 text-sm text-gray-500">
                            This screen bridges teacher intake with reviewer action and eventual publication into public-facing knowledge routes.
                            </p>
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-3">
                        <Button asChild variant="secondary">
                            <Link to="/portal/review">Open review queue</Link>
                        </Button>
                        {submission.linkedDocumentId ? (
                            <Button asChild>
                                <Link to={`/documents/${submission.linkedDocumentId}`}>Open published document</Link>
                            </Button>
                        ) : null}
                    </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                    <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950">
                        <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                            <GitPullRequest size={16} />
                            Reviewer handoff
                        </div>
                        <div className="mt-3 space-y-2 text-sm text-gray-500">
                            <p>Latest reviewer: {relatedReviewTask?.reviewerName ?? 'Not assigned yet'}</p>
                            <p>Review reason: {relatedReviewTask?.reason ?? 'Reviewer notes will appear here once the queue picks up this submission.'}</p>
                            <p>
                                Publication target:{' '}
                                {submission.linkedDocumentId
                                    ? `document ${submission.linkedDocumentId}`
                                    : submission.supplemental.visibilityScope === 'public'
                                      ? 'public assistant after approval'
                                      : 'internal knowledge routes only'}
                            </p>
                        </div>
                    </div>

                    <div className="rounded-2xl border border-brand-200 bg-brand-50 p-4 dark:border-brand-900 dark:bg-brand-950">
                        <div className="flex items-center gap-2 text-sm font-semibold text-brand-800 dark:text-brand-200">
                            <Sparkles size={16} />
                            Submission readiness
                        </div>
                        <div className="mt-3 space-y-2 text-sm text-brand-700 dark:text-brand-300">
                            <p>Confidence score is always present, even when extraction falls back to defaults.</p>
                            <p>Optional temporal fields can remain empty if the source does not explicitly include them.</p>
                            <p>System metadata stays read-only and helps reviewers verify provenance before publication.</p>
                        </div>
                    </div>
                </div>
            </Card>

            <div className="grid gap-6 xl:grid-cols-2">
                <MetadataPanel
                    title="Editorial package"
                    entries={[
                        { label: 'Source type', value: submission.sourceType },
                        { label: 'Visibility target', value: submission.supplemental.visibilityScope },
                        { label: 'Issuing unit', value: submission.supplemental.issuingUnit },
                        { label: 'Tags', value: submission.supplemental.tags.join(', ') || 'No tags yet' },
                        { label: 'Reviewer notes', value: submission.supplemental.notes || 'No notes provided' },
                    ]}
                />
                <MetadataPanel
                    title="Extraction diagnostics"
                    entries={[
                        { label: 'Document type', value: submission.temporal.documentType },
                        { label: 'Confidence', value: formatPercent(submission.temporal.confidence) },
                        { label: 'Reasoning', value: submission.temporal.reasoning || 'No reasoning returned' },
                        { label: 'Academic year', value: submission.temporal.academicYear },
                        { label: 'Document number', value: submission.temporal.documentNumber },
                    ]}
                />
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
                <Card className="space-y-4">
                    <div className="text-base font-semibold text-gray-900 dark:text-white">Traceability linkage</div>
                    <div className="space-y-3 text-sm text-gray-600 dark:text-gray-300">
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Review task:</span>{' '}
                            {submission.traceability?.reviewTaskId ? (
                                <Link className="text-brand-700 hover:text-brand-800 dark:text-brand-300" to="/portal/review">
                                    {submission.traceability.reviewTaskId}
                                </Link>
                            ) : (
                                'Not linked'
                            )}
                        </div>
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Published document:</span>{' '}
                            {submission.traceability?.publishedDocumentId ? (
                                <Link className="text-brand-700 hover:text-brand-800 dark:text-brand-300" to={`/documents/${submission.traceability.publishedDocumentId}`}>
                                    {submission.traceability.publishedDocumentId}
                                </Link>
                            ) : (
                                'Not published yet'
                            )}
                        </div>
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Reviewed by:</span>{' '}
                            {submission.traceability?.reviewedByName ?? 'Not assigned'}
                        </div>
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Published at:</span>{' '}
                            {formatDateTime(submission.traceability?.publishedAt)}
                        </div>
                        <div>
                            <span className="font-semibold text-gray-900 dark:text-white">Decision reason:</span>{' '}
                            {submission.traceability?.publicationReason ?? 'No publication reason recorded'}
                        </div>
                    </div>
                </Card>

                <Card className="space-y-4">
                    <div className="text-base font-semibold text-gray-900 dark:text-white">Metadata diff summary</div>
                    <div className="space-y-3">
                        {diffSummary.length > 0 ? (
                            diffSummary.map((row) => (
                                <div key={row.label} className="rounded-2xl border border-brand-200 bg-brand-50 p-4 dark:border-brand-900 dark:bg-brand-950">
                                    <div className="text-sm font-semibold text-gray-900 dark:text-white">{row.label}</div>
                                    <div className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                                        Extracted: {row.extracted}
                                    </div>
                                    <div className="mt-1 text-sm text-brand-800 dark:text-brand-200">
                                        Reviewer confirmed: {row.edited}
                                    </div>
                                </div>
                            ))
                        ) : currentVersion?.changeHighlights?.length ? (
                            currentVersion.changeHighlights.map((highlight) => (
                                <div key={highlight} className="rounded-2xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-900 dark:border-brand-900 dark:bg-brand-950 dark:text-brand-100">
                                    {highlight}
                                </div>
                            ))
                        ) : (
                            <p className="text-sm text-gray-500">No reviewer metadata diff has been recorded for this submission yet.</p>
                        )}
                    </div>
                </Card>
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
                <MetadataPanel
                    title="Temporal review fields"
                    entries={[
                        { label: 'Valid from', value: submission.temporal.validFrom },
                        { label: 'Valid until', value: submission.temporal.validUntil },
                        { label: 'Cohort years', value: submission.temporal.cohortYears.join(', ') || 'Not detected' },
                        { label: 'Amends documents', value: submission.temporal.amendsDocuments.join(', ') || 'None' },
                    ]}
                />
                <MetadataPanel
                    title="System provenance"
                    entries={[
                        { label: 'File source', value: submission.system.fileSource },
                        { label: 'Indexed at', value: formatDateTime(submission.system.indexedAt) },
                        { label: 'Content hash', value: submission.system.contentHash },
                        { label: 'Version', value: submission.system.versionNumber },
                        { label: 'Archived', value: submission.system.isArchived ? 'Yes' : 'No' },
                    ]}
                />
            </div>

            <Card className="space-y-4">
                <div className="text-base font-semibold text-gray-900 dark:text-white">Workflow timeline</div>
                <StatusTimeline steps={timelineSteps} />
            </Card>
        </div>
    )
}
