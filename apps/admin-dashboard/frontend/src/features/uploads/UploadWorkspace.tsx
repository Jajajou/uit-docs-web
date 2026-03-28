import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { CheckCircle2, FileCog, FileSearch, LockKeyhole, Sparkles } from 'lucide-react'
import { useSessionQuery } from '@/entities/auth/queries'
import { hasRequiredInternalEmail } from '@/app/config/routes'
import type { DocumentLifecycleStatus, ProcessingStatus, VisibilityScope } from '@/entities/documents/types'
import { useFileUploadMutation, useTextUploadMutation, useUrlUploadMutation } from '@/entities/submissions/queries'
import type { Submission, UploadSourceType } from '@/entities/submissions/types'
import { parseTagInput, validateUploadDraft, type UploadDraftFormValues } from '@/features/uploads/schema'
import { formatDateTime, formatPercent } from '@/shared/lib/format'
import { Badge, Button, Card, Checkbox, FileDropzone, Input, MetadataField, Select, StatusTimeline, Tabs, TabsContent, TabsList, TabsTrigger, Textarea } from '@/shared/ui'

const defaultValues: UploadDraftFormValues = {
    sourceType: 'file',
    title: '',
    fileCount: 0,
    rawText: '',
    url: '',
    issuingUnit: '',
    visibilityScope: 'internal',
    tagsInput: '',
    notes: '',
    confirmOwnership: false,
    confirmReviewReady: false,
}

const visibilityOptions = [
    { value: 'internal', label: 'Internal only' },
    { value: 'public', label: 'Public after approval' },
] satisfies Array<{ value: VisibilityScope; label: string }>

const sourceGuidance: Record<UploadSourceType, { title: string; description: string; rules: string[] }> = {
    file: {
        title: 'Document upload',
        description: 'Best for official PDFs, scanned notices and structured handbooks.',
        rules: [
            'Use the latest official file from faculty or university channels.',
            'OCR and temporal extraction will run after upload.',
            'Public visibility still requires reviewer approval.',
        ],
    },
    text: {
        title: 'Bulletin text',
        description: 'Best for quick notices copied from internal announcements before the source file arrives.',
        rules: [
            'Include the full heading and any effective dates in the pasted text.',
            'Keep copied sections coherent so extraction can infer document type.',
            'Reviewer should replace text-only submissions with the source file later if available.',
        ],
    },
    url: {
        title: 'Official source URL',
        description: 'Best for university pages that already host the canonical version of the content.',
        rules: [
            'Only submit official UIT or faculty URLs.',
            'The review queue should confirm the page still matches the intended audience and time range.',
            'Use public visibility only when the page is safe to cite in student-facing chat.',
        ],
    },
}

function mapProcessingState(status?: ProcessingStatus) {
    switch (status) {
        case 'failed':
            return 'failed' as const
        case 'completed':
            return 'done' as const
        case 'extracting':
        case 'indexing':
        case 'uploading':
            return 'current' as const
        default:
            return 'pending' as const
    }
}

function mapReviewState(status?: DocumentLifecycleStatus) {
    switch (status) {
        case 'approved':
            return 'done' as const
        case 'rejected':
            return 'failed' as const
        case 'pending_review':
            return 'current' as const
        default:
            return 'pending' as const
    }
}

function getReadinessTone(score: number) {
    if (score >= 4) {
        return 'success' as const
    }

    if (score >= 2) {
        return 'warning' as const
    }

    return 'danger' as const
}

function buildTimeline(
    sourceType: UploadSourceType,
    sourceReady: boolean,
    visibilityScope: VisibilityScope,
    latestSubmission?: Submission,
) {
    const sourceLabel =
        sourceType === 'file' ? 'Official file attached' : sourceType === 'text' ? 'Bulletin text prepared' : 'Source URL linked'

    return [
        {
            id: 'source',
            label: sourceLabel,
            description: sourceReady ? 'Draft has enough source material for submission.' : 'Complete the source step before sending for review.',
            state: sourceReady ? ('done' as const) : ('current' as const),
        },
        {
            id: 'extraction',
            label: 'Temporal extraction',
            description: latestSubmission
                ? `${latestSubmission.temporal.documentType} detected with ${formatPercent(latestSubmission.temporal.confidence)} confidence.`
                : 'System will infer document type, temporal metadata and diagnostics.',
            state: mapProcessingState(latestSubmission?.processingStatus),
        },
        {
            id: 'review',
            label: 'Human approval',
            description: latestSubmission
                ? `Submission is ${latestSubmission.lifecycleStatus.replace('_', ' ')} in the internal review queue.`
                : 'Operator review is required before any document becomes trusted in chat.',
            state: mapReviewState(latestSubmission?.lifecycleStatus),
        },
        {
            id: 'publish',
            label: 'Visibility release',
            description:
                visibilityScope === 'public'
                    ? 'Approved document can be promoted to student-facing chat and public search.'
                    : 'Approved document remains restricted to internal staff and operators.',
            state:
                latestSubmission?.lifecycleStatus === 'approved'
                    ? ('done' as const)
                    : latestSubmission?.lifecycleStatus === 'rejected'
                      ? ('failed' as const)
                      : ('pending' as const),
        },
    ]
}

export function UploadWorkspace({ scenario }: { scenario?: string }) {
    const sessionQuery = useSessionQuery({ scenario })
    const [files, setFiles] = useState<File[]>([])
    const {
        register,
        handleSubmit,
        watch,
        clearErrors,
        setError,
        setValue,
        reset,
        formState: { errors },
    } = useForm<UploadDraftFormValues>({
        defaultValues,
    })

    const sourceType = watch('sourceType')
    const title = watch('title')
    const issuingUnit = watch('issuingUnit')
    const visibilityScope = watch('visibilityScope')
    const tagsInput = watch('tagsInput')
    const notes = watch('notes')
    const confirmOwnership = watch('confirmOwnership')
    const confirmReviewReady = watch('confirmReviewReady')
    const rawText = watch('rawText')
    const url = watch('url')

    const fileUpload = useFileUploadMutation({ scenario })
    const textUpload = useTextUploadMutation({ scenario })
    const urlUpload = useUrlUploadMutation({ scenario })
    const latestSubmission = fileUpload.data ?? textUpload.data ?? urlUpload.data
    const uploadError = fileUpload.error ?? textUpload.error ?? urlUpload.error
    const isSubmitting = fileUpload.isPending || textUpload.isPending || urlUpload.isPending

    const tags = useMemo(() => parseTagInput(tagsInput), [tagsInput])
    const sourceReady =
        sourceType === 'file' ? files.length > 0 : sourceType === 'text' ? rawText.trim().length >= 80 : Boolean(url.trim())
    const readinessScore = [Boolean(title.trim()), sourceReady, Boolean(issuingUnit.trim()), confirmOwnership, confirmReviewReady].filter(Boolean).length
    const readinessTone = getReadinessTone(readinessScore)
    const timelineSteps = useMemo(
        () => buildTimeline(sourceType, sourceReady, visibilityScope, latestSubmission),
        [latestSubmission, sourceReady, sourceType, visibilityScope],
    )
    const uploader = sessionQuery.data?.user
    const isGmAccount = uploader ? hasRequiredInternalEmail(uploader.role, uploader.email) : false
    const currentGuidance = sourceGuidance[sourceType]

    const resetDraft = () => {
        reset(defaultValues)
        setFiles([])
    }

    const submitDraft = handleSubmit(async (values) => {
        clearErrors()
        const result = validateUploadDraft(values)

        if (!result.success) {
            for (const issue of result.error.issues) {
                const field = issue.path[0]

                if (typeof field === 'string') {
                    setError(field as keyof UploadDraftFormValues, {
                        type: 'manual',
                        message: issue.message,
                    })
                }
            }

            return
        }

        const basePayload = {
            sourceType: result.data.sourceType,
            title: result.data.title,
            issuingUnit: result.data.issuingUnit,
            visibilityScope: result.data.visibilityScope,
            tags: result.data.tags,
            notes: result.data.notes,
        }

        try {
            if (result.data.sourceType === 'file') {
                await fileUpload.mutateAsync({
                    ...basePayload,
                    fileName: files[0]?.name,
                })
                setFiles([])
                setValue('fileCount', 0)
            }

            if (result.data.sourceType === 'text') {
                await textUpload.mutateAsync({
                    ...basePayload,
                    content: result.data.rawText,
                })
                setValue('rawText', '')
            }

            if (result.data.sourceType === 'url') {
                await urlUpload.mutateAsync({
                    ...basePayload,
                    url: result.data.url,
                })
                setValue('url', '')
            }
        } catch {
            // Expected mock/API errors are surfaced through mutation state and rendered in the workspace banner.
        }
    })

    return (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(22rem,0.85fr)]">
            <div className="space-y-6">
                <Card className="space-y-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="space-y-1">
                            <div className="flex items-center gap-2">
                                <Badge tone="brand">Lecturer intake</Badge>
                                <Badge tone={readinessTone}>Draft readiness {readinessScore}/5</Badge>
                            </div>
                            <h2 className="text-xl font-semibold text-gray-950 dark:text-white">Prepare a submission for reviewer approval</h2>
                            <p className="text-sm text-gray-500">
                                This flow stays aligned with the current temporal metadata contract. Time fields remain optional and reviewers only
                                confirm them when the source supports it.
                            </p>
                        </div>
                        <Button asChild variant="secondary">
                            <Link to="/portal/submissions">View submission queue</Link>
                        </Button>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="rounded-2xl border border-brand-200 bg-brand-50 p-4 dark:border-brand-900 dark:bg-brand-950">
                            <div className="flex items-center gap-2 text-sm font-semibold text-brand-800 dark:text-brand-200">
                                <LockKeyhole size={16} />
                                Internal account rule
                            </div>
                            <p className="mt-2 text-sm text-brand-700 dark:text-brand-300">
                                Lecturer, operator and admin uploads must come from an internal account ending with `@gm.uit.edu.vn`.
                            </p>
                        </div>
                        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950">
                            <div className="text-sm font-semibold text-gray-900 dark:text-white">Current uploader</div>
                            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                                {uploader ? `${uploader.name} - ${uploader.email}` : 'Loading session...'}
                            </p>
                            {uploader ? (
                                <p className="mt-1 text-xs text-gray-500">
                                    {isGmAccount ? 'Eligible for internal upload workflow.' : 'Role is authenticated but does not match the internal mail rule.'}
                                </p>
                            ) : null}
                        </div>
                    </div>
                </Card>

                <Card className="space-y-5">
                    <div className="space-y-1">
                        <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                            <FileCog size={16} />
                            Source intake
                        </div>
                        <p className="text-sm text-gray-500">{currentGuidance.description}</p>
                    </div>

                    <Tabs
                        value={sourceType}
                        onValueChange={(value) => {
                            setValue('sourceType', value as UploadSourceType, { shouldDirty: true })
                            clearErrors(['fileCount', 'rawText', 'url'])
                        }}
                    >
                        <TabsList>
                            <TabsTrigger value="file">File</TabsTrigger>
                            <TabsTrigger value="text">Text</TabsTrigger>
                            <TabsTrigger value="url">URL</TabsTrigger>
                        </TabsList>

                        <TabsContent value="file" className="space-y-3">
                            <FileDropzone
                                value={files}
                                onChange={(nextFiles) => {
                                    setFiles(nextFiles)
                                    setValue('fileCount', nextFiles.length, { shouldDirty: true })
                                    clearErrors('fileCount')
                                }}
                            />
                            {errors.fileCount ? <p className="text-xs font-medium text-error-600">{errors.fileCount.message}</p> : null}
                        </TabsContent>

                        <TabsContent value="text">
                            <Textarea
                                label="Raw bulletin text"
                                placeholder="Paste the official notice, including title, issuing unit and effective dates when available..."
                                error={errors.rawText?.message}
                                {...register('rawText')}
                            />
                        </TabsContent>

                        <TabsContent value="url">
                            <Input
                                label="Official source URL"
                                placeholder="https://uit.edu.vn/..."
                                error={errors.url?.message}
                                {...register('url')}
                            />
                        </TabsContent>
                    </Tabs>

                    <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">{currentGuidance.title}</div>
                        <ul className="mt-3 space-y-2 text-sm text-gray-500">
                            {currentGuidance.rules.map((rule) => (
                                <li key={rule} className="flex items-start gap-2">
                                    <Sparkles size={14} className="mt-0.5 text-brand-600" />
                                    <span>{rule}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                </Card>

                <Card className="space-y-5">
                    <div className="space-y-1">
                        <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                            <FileSearch size={16} />
                            Editorial metadata
                        </div>
                        <p className="text-sm text-gray-500">Only collect the fields editors can actually guarantee before extraction. Temporal details remain optional.</p>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                        <Input label="Submission title" placeholder="Thong bao hoc phi hoc ky 2" error={errors.title?.message} {...register('title')} />
                        <Input label="Issuing unit" placeholder="Phong Dao tao Dai hoc" error={errors.issuingUnit?.message} {...register('issuingUnit')} />
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                        <Select
                            label="Visibility target"
                            options={visibilityOptions}
                            error={errors.visibilityScope?.message}
                            {...register('visibilityScope')}
                        />
                        <Input
                            label="Tags"
                            placeholder="hoc-phi, dang-ky-mon-hoc"
                            hint="Comma-separated labels help reviewers route the document faster."
                            error={errors.tagsInput?.message}
                            {...register('tagsInput')}
                        />
                    </div>

                    <Textarea
                        label="Reviewer notes"
                        placeholder="Optional context for the reviewer, for example which student group should see this first."
                        error={errors.notes?.message}
                        {...register('notes')}
                    />

                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950">
                            <div className="text-sm font-semibold text-gray-900 dark:text-white">Checklist before submit</div>
                            <div className="mt-4 space-y-3">
                                <Checkbox
                                    label="I confirm this source comes from an official UIT or faculty channel."
                                    hint="Required for every lecturer submission."
                                    checked={confirmOwnership}
                                    onChange={(event) => {
                                        setValue('confirmOwnership', event.target.checked, { shouldDirty: true })
                                        clearErrors('confirmOwnership')
                                    }}
                                />
                                {errors.confirmOwnership ? <p className="text-xs font-medium text-error-600">{errors.confirmOwnership.message}</p> : null}
                                <Checkbox
                                    label="I understand the document enters a human review queue before it becomes trusted."
                                    hint="Public visibility never skips operator approval."
                                    checked={confirmReviewReady}
                                    onChange={(event) => {
                                        setValue('confirmReviewReady', event.target.checked, { shouldDirty: true })
                                        clearErrors('confirmReviewReady')
                                    }}
                                />
                                {errors.confirmReviewReady ? <p className="text-xs font-medium text-error-600">{errors.confirmReviewReady.message}</p> : null}
                            </div>
                        </div>

                        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950">
                            <div className="text-sm font-semibold text-gray-900 dark:text-white">Draft snapshot</div>
                            <div className="mt-4 flex flex-wrap gap-2">
                                <Badge tone="neutral">{sourceType}</Badge>
                                <Badge tone={visibilityScope === 'public' ? 'brand' : 'neutral'}>{visibilityScope}</Badge>
                                {tags.slice(0, 4).map((tag) => (
                                    <Badge key={tag} tone="warning">
                                        {tag}
                                    </Badge>
                                ))}
                                {tags.length === 0 ? <Badge tone="neutral">No tags yet</Badge> : null}
                            </div>
                            <p className="mt-4 text-sm text-gray-500">
                                Notes length: {notes.trim().length} characters. Reviewers will still rely on extracted `document_type`, confidence and reasoning.
                            </p>
                        </div>
                    </div>

                    <div className="flex flex-wrap justify-end gap-3">
                        {uploadError ? (
                            <div className="mr-auto rounded-xl border border-error-200 bg-error-50 px-3 py-2 text-xs text-error-700 dark:border-error-800 dark:bg-error-950 dark:text-error-300">
                                {uploadError.message}
                            </div>
                        ) : null}
                        <Button variant="ghost" onClick={resetDraft} type="button">
                            Reset draft
                        </Button>
                        <Button isLoading={isSubmitting} onClick={submitDraft} type="button">
                            Submit for review
                        </Button>
                    </div>
                </Card>
            </div>

            <div className="space-y-6">
                <Card className="space-y-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                        <CheckCircle2 size={16} />
                        Approval timeline
                    </div>
                    <StatusTimeline steps={timelineSteps} />
                </Card>

                <Card className="space-y-4">
                    <div className="flex items-center justify-between gap-3">
                        <div>
                            <div className="text-sm font-semibold text-gray-900 dark:text-white">Latest extraction result</div>
                            <p className="mt-1 text-sm text-gray-500">
                                The system fills mandatory temporal metadata even when the source has weak date signals.
                            </p>
                        </div>
                        <Badge tone={latestSubmission ? 'success' : 'neutral'}>{latestSubmission ? latestSubmission.processingStatus : 'not submitted'}</Badge>
                    </div>

                    <div className="grid gap-3">
                        <MetadataField label="Document type" value={latestSubmission?.temporal.documentType ?? 'other'} />
                        <MetadataField
                            label="Extraction confidence"
                            value={latestSubmission ? formatPercent(latestSubmission.temporal.confidence) : 'Pending extraction'}
                            hint="`confidence` is always present even when the extractor falls back to defaults."
                        />
                        <MetadataField
                            label="Temporal reasoning"
                            value={latestSubmission?.temporal.reasoning ?? 'Reasoning will appear after extraction.'}
                        />
                        <MetadataField
                            label="Document number"
                            value={latestSubmission?.temporal.documentNumber ?? 'Optional, only if detected from source.'}
                        />
                        <MetadataField
                            label="Indexed at"
                            value={latestSubmission ? formatDateTime(latestSubmission.system.indexedAt) : 'Pending'}
                        />
                        <MetadataField label="Version" value={latestSubmission?.system.versionNumber ?? 1} />
                    </div>
                </Card>

                <Card className="space-y-4">
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">Submission policy</div>
                    <div className="space-y-3 text-sm text-gray-500">
                        <p>`document_type`, `extraction_method`, `confidence` and `reasoning` are always generated by the system.</p>
                        <p>`valid_from`, `valid_until`, `academic_year`, `cohort_years`, `document_number` and `amends_documents` stay optional.</p>
                        <p>`file_source`, `indexed_at`, `content_hash`, `is_archived` and `version_number` remain read-only in the UI.</p>
                    </div>
                </Card>
            </div>
        </div>
    )
}
