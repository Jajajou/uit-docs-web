import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ClipboardCheck, ClipboardList, Search, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { mapTemporalMetadataToDto } from '@/entities/documents/mappers'
import { formatStatusLabel, getLifecycleTone, getVisibilityTone } from '@/entities/documents/presentation'
import { useSessionQuery } from '@/entities/auth/queries'
import { useReviewDecisionMutation, useReviewTasksQuery } from '@/entities/reviews/queries'
import type { ReviewTask } from '@/entities/reviews/types'
import { formatDateTime, formatPercent } from '@/shared/lib/format'
import { Badge, Button, Card, EmptyState, Input, Tabs, TabsContent, TabsList, TabsTrigger, Textarea } from '@/shared/ui'

type ReviewStatusFilter = 'all' | 'pending_review' | 'approved' | 'rejected'
type DecisionStatus = Extract<ReviewTask['status'], 'pending_review' | 'approved' | 'rejected'>

function getDiffRows(task: ReviewTask) {
    return [
        {
            label: 'Document type',
            extracted: task.extractedTemporal.documentType,
            edited: task.editedTemporal.documentType,
        },
        {
            label: 'Valid from',
            extracted: task.extractedTemporal.validFrom ?? 'Not detected',
            edited: task.editedTemporal.validFrom ?? 'Not confirmed',
        },
        {
            label: 'Valid until',
            extracted: task.extractedTemporal.validUntil ?? 'Not detected',
            edited: task.editedTemporal.validUntil ?? 'Not confirmed',
        },
        {
            label: 'Academic year',
            extracted: task.extractedTemporal.academicYear ?? 'Not detected',
            edited: task.editedTemporal.academicYear ?? 'Not confirmed',
        },
        {
            label: 'Cohort years',
            extracted: task.extractedTemporal.cohortYears.join(', ') || 'Not detected',
            edited: task.editedTemporal.cohortYears.join(', ') || 'Not confirmed',
        },
        {
            label: 'Document number',
            extracted: task.extractedTemporal.documentNumber ?? 'Not detected',
            edited: task.editedTemporal.documentNumber ?? 'Not confirmed',
        },
        {
            label: 'Amends documents',
            extracted: task.extractedTemporal.amendsDocuments.join(', ') || 'None',
            edited: task.editedTemporal.amendsDocuments.join(', ') || 'None',
        },
    ].map((row) => ({
        ...row,
        changed: row.extracted !== row.edited,
    }))
}

function getDecisionSummary(status: DecisionStatus, task: ReviewTask) {
    if (status === 'approved' && task.visibilityScope === 'public') {
        return 'Approved items with public visibility can move into student-facing assistant answers once published.'
    }

    if (status === 'approved') {
        return 'Approved items stay available to internal staff and admins.'
    }

    if (status === 'rejected') {
        return 'Rejected items should never appear in trusted assistant answers.'
    }

    return 'Requesting changes keeps the submission out of trusted assistant answers until the teacher resubmits and the reviewer approves it.'
}

export function ReviewQueue({ scenario }: { scenario?: string }) {
    const reviewQuery = useReviewTasksQuery({ scenario })
    const sessionQuery = useSessionQuery({ scenario })
    const reviewDecisionMutation = useReviewDecisionMutation({ scenario })
    const [searchValue, setSearchValue] = useState('')
    const [activeStatus, setActiveStatus] = useState<ReviewStatusFilter>('all')
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
    const [decisionNotes, setDecisionNotes] = useState<Record<string, string>>({})
    const deferredSearch = useDeferredValue(searchValue)

    const filteredTasks = useMemo(() => {
        const tasks = reviewQuery.data ?? []
        const normalizedSearch = deferredSearch.trim().toLowerCase()

        return tasks.filter((task) => {
            const matchesStatus = activeStatus === 'all' ? true : task.status === activeStatus
            const matchesSearch =
                normalizedSearch.length === 0 ||
                task.title.toLowerCase().includes(normalizedSearch) ||
                task.submittedByName.toLowerCase().includes(normalizedSearch) ||
                task.reviewerName.toLowerCase().includes(normalizedSearch)

            return matchesStatus && matchesSearch
        })
    }, [activeStatus, deferredSearch, reviewQuery.data])

    useEffect(() => {
        if (filteredTasks.length === 0) {
            setSelectedTaskId(null)
            return
        }

        if (!selectedTaskId || !filteredTasks.some((task) => task.id === selectedTaskId)) {
            setSelectedTaskId(filteredTasks[0].id)
        }
    }, [filteredTasks, selectedTaskId])

    useEffect(() => {
        if (!reviewQuery.data) {
            return
        }

        setDecisionNotes((current) => {
            const next = { ...current }

            for (const task of reviewQuery.data) {
                if (next[task.id] === undefined) {
                    next[task.id] = task.reason
                }
            }

            return next
        })
    }, [reviewQuery.data])

    const selectedTask = filteredTasks.find((task) => task.id === selectedTaskId) ?? filteredTasks[0]
    const isAdminBreakGlass = sessionQuery.data?.user.role === 'admin'

    const handleDecision = async (task: ReviewTask, status: DecisionStatus) => {
        try {
            const updatedTask = await reviewDecisionMutation.mutateAsync({
                reviewId: task.id,
                payload: {
                    status,
                    reason: decisionNotes[task.id]?.trim() || task.reason,
                    editedTemporalMetadata: mapTemporalMetadataToDto(task.editedTemporal),
                },
            })

            toast.success(`Review updated: ${formatStatusLabel(updatedTask.status)}`, {
                description: status === 'approved' ? 'The linked submission and published document have been refreshed.' : getDecisionSummary(status, task),
            })
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Unable to persist the review decision.'
            toast.error('Review update failed', { description: message })
        }
    }

    if (reviewQuery.isLoading) {
        return <Card className="h-80 animate-pulse" />
    }

    if (reviewQuery.isError) {
        return <Card className="text-sm text-error-700 dark:text-error-300">{reviewQuery.error.message}</Card>
    }

    return (
        <div className="space-y-6">
            <Card className="space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-1">
                        <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                            <ClipboardCheck size={16} />
                            Reviewer decision workspace
                        </div>
                        <p className="text-sm text-gray-500">
                            This queue connects teacher submissions to publication outcomes. Reviewers validate metadata, decision status and public-chat eligibility.
                        </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Badge tone="neutral">{reviewQuery.data?.length ?? 0} tasks</Badge>
                        <Badge tone="warning">{reviewQuery.data?.filter((task) => task.status === 'pending_review').length ?? 0} pending</Badge>
                        <Badge tone="success">{reviewQuery.data?.filter((task) => task.status === 'approved').length ?? 0} approved</Badge>
                    </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto]">
                    <Input
                        label="Search review tasks"
                        value={searchValue}
                        onChange={(event) => setSearchValue(event.target.value)}
                        placeholder="Search by title, requester or reviewer..."
                    />
                    <div className="flex items-end gap-2">
                        <Button asChild variant="secondary">
                            <Link to="/portal/submissions">Open submissions</Link>
                        </Button>
                    </div>
                </div>

                <Tabs value={activeStatus} onValueChange={(value) => setActiveStatus(value as ReviewStatusFilter)}>
                    <TabsList>
                        <TabsTrigger value="all">All</TabsTrigger>
                        <TabsTrigger value="pending_review">Pending</TabsTrigger>
                        <TabsTrigger value="approved">Approved</TabsTrigger>
                        <TabsTrigger value="rejected">Rejected</TabsTrigger>
                    </TabsList>
                    <TabsContent value={activeStatus} className="mt-4">
                        {isAdminBreakGlass ? (
                            <div className="mb-4 rounded-2xl border border-warning-200 bg-warning-50 p-4 text-sm text-warning-900 dark:border-warning-800 dark:bg-warning-950 dark:text-warning-100">
                                <div className="font-semibold">Break-glass support mode</div>
                                <p className="mt-2">
                                    Review decisions remain admin-owned and every decision stays visible in audit logs.
                                </p>
                            </div>
                        ) : null}
                        {filteredTasks.length === 0 ? (
                            <EmptyState
                                icon={ClipboardList}
                                title="No review tasks"
                                description="This filter combination returns no items in the current scenario."
                            />
                        ) : (
                            <div className="grid gap-6 xl:grid-cols-[21rem_minmax(0,1fr)]">
                                <div className="space-y-3">
                                    {filteredTasks.map((task) => {
                                        const isSelected = selectedTask?.id === task.id

                                        return (
                                            <button
                                                key={task.id}
                                                type="button"
                                                onClick={() => setSelectedTaskId(task.id)}
                                                className={`w-full rounded-2xl border p-4 text-left transition ${
                                                    isSelected
                                                        ? 'border-brand-300 bg-brand-50 dark:border-brand-800 dark:bg-brand-950'
                                                        : 'border-gray-200 bg-white hover:bg-gray-50 dark:border-gray-800 dark:bg-gray-900 dark:hover:bg-gray-800'
                                                }`}
                                            >
                                                <div className="flex flex-wrap items-start justify-between gap-2">
                                                    <div className="space-y-1">
                                                        <div className="font-medium text-gray-900 dark:text-white">{task.title}</div>
                                                        <div className="text-xs text-gray-500">{formatDateTime(task.createdAt)}</div>
                                                    </div>
                                                    <Badge tone={getLifecycleTone(task.status)}>{formatStatusLabel(task.status)}</Badge>
                                                </div>
                                                <div className="mt-3 flex flex-wrap gap-2">
                                                    <Badge tone={getVisibilityTone(task.visibilityScope)}>{task.visibilityScope}</Badge>
                                                    <Badge tone="neutral">{task.sourceType}</Badge>
                                                    <Badge tone="brand">{formatPercent(task.confidence)}</Badge>
                                                </div>
                                                <div className="mt-3 text-sm text-gray-500">Requester: {task.submittedByName}</div>
                                            </button>
                                        )
                                    })}
                                </div>

                                {selectedTask ? (
                                    <ReviewTaskDetail
                                        task={selectedTask}
                                        decisionNote={decisionNotes[selectedTask.id] ?? selectedTask.reason}
                                        onDecisionNoteChange={(value) =>
                                            setDecisionNotes((current) => ({ ...current, [selectedTask.id]: value }))
                                        }
                                        onDecision={handleDecision}
                                        isAdminBreakGlass={isAdminBreakGlass}
                                        isSubmitting={reviewDecisionMutation.isPending && reviewDecisionMutation.variables?.reviewId === selectedTask.id}
                                        submitError={
                                            reviewDecisionMutation.variables?.reviewId === selectedTask.id ? reviewDecisionMutation.error?.message : undefined
                                        }
                                    />
                                ) : null}
                            </div>
                        )}
                    </TabsContent>
                </Tabs>
            </Card>
        </div>
    )
}

function ReviewTaskDetail({
    task,
    decisionNote,
    onDecisionNoteChange,
    onDecision,
    isAdminBreakGlass,
    isSubmitting,
    submitError,
}: {
    task: ReviewTask
    decisionNote: string
    onDecisionNoteChange: (value: string) => void
    onDecision: (task: ReviewTask, status: DecisionStatus) => Promise<void>
    isAdminBreakGlass: boolean
    isSubmitting: boolean
    submitError?: string
}) {
    return (
        <div className="space-y-6">
            <Card className="space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-2">
                        <div className="flex flex-wrap gap-2">
                            <Badge tone={getLifecycleTone(task.status)}>{formatStatusLabel(task.status)}</Badge>
                            <Badge tone={getVisibilityTone(task.visibilityScope)}>{task.visibilityScope}</Badge>
                            <Badge tone="neutral">{task.sourceType}</Badge>
                            <Badge tone="brand">Confidence {formatPercent(task.confidence)}</Badge>
                        </div>
                        <div>
                            <h2 className="text-xl font-semibold text-gray-950 dark:text-white">{task.title}</h2>
                            <p className="mt-1 text-sm text-gray-500">
                                Submitted by {task.submittedByName} ({task.submittedByEmail}) and currently reviewed by {task.reviewerName}.
                            </p>
                        </div>
                    </div>
                    <div className="flex flex-wrap gap-3">
                        <Button asChild variant="secondary">
                            <Link to={`/portal/submissions/${task.submissionId}`}>Open submission detail</Link>
                        </Button>
                        {task.publishedDocumentId ? (
                            <Button asChild>
                                <Link to={`/documents/${task.publishedDocumentId}`}>Open published document</Link>
                            </Button>
                        ) : null}
                    </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">Reviewer note</div>
                        <Textarea
                            className="mt-3"
                            value={decisionNote}
                            onChange={(event) => onDecisionNoteChange(event.target.value)}
                                placeholder="Capture the decision rationale or the follow-up required from the teacher."
                        />
                    </div>
                    <div className="rounded-2xl border border-brand-200 bg-brand-50 p-4 dark:border-brand-900 dark:bg-brand-950">
                        <div className="flex items-center gap-2 text-sm font-semibold text-brand-800 dark:text-brand-200">
                            <ShieldCheck size={16} />
                            Public impact
                        </div>
                        <p className="mt-2 text-sm text-brand-700 dark:text-brand-300">{getDecisionSummary(task.status, task)}</p>
                    </div>
                </div>

                <div className="flex flex-wrap gap-3">
                    <Button isLoading={isSubmitting} variant="primary" onClick={() => onDecision(task, 'approved')}>
                        {isAdminBreakGlass ? 'Approve (support override)' : 'Approve'}
                    </Button>
                    <Button isLoading={isSubmitting} variant="outline" onClick={() => onDecision(task, 'pending_review')}>
                        {isAdminBreakGlass ? 'Request changes (support override)' : 'Request changes'}
                    </Button>
                    <Button isLoading={isSubmitting} variant="danger" onClick={() => onDecision(task, 'rejected')}>
                        {isAdminBreakGlass ? 'Reject (support override)' : 'Reject'}
                    </Button>
                </div>

                {submitError ? (
                    <div className="rounded-2xl border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-700 dark:border-error-800 dark:bg-error-950 dark:text-error-200">
                        {submitError}
                    </div>
                ) : null}
            </Card>

            <Card className="space-y-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                    <Search size={16} />
                    Metadata diff review
                </div>
                <div className="space-y-3">
                    {getDiffRows(task).map((row) => (
                        <div
                            key={row.label}
                            className={`rounded-2xl border p-4 ${
                                row.changed
                                    ? 'border-brand-200 bg-brand-50 dark:border-brand-900 dark:bg-brand-950'
                                    : 'border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-950'
                            }`}
                        >
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div className="text-sm font-semibold text-gray-900 dark:text-white">{row.label}</div>
                                <Badge tone={row.changed ? 'brand' : 'neutral'}>{row.changed ? 'Changed' : 'No change'}</Badge>
                            </div>
                            <div className="mt-3 grid gap-3 md:grid-cols-2">
                                <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
                                    <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Extracted</div>
                                    <div className="mt-2 text-sm text-gray-700 dark:text-gray-200">{row.extracted}</div>
                                </div>
                                <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900">
                                    <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Reviewer confirmed</div>
                                    <div className="mt-2 text-sm text-gray-700 dark:text-gray-200">{row.edited}</div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </Card>
        </div>
    )
}
