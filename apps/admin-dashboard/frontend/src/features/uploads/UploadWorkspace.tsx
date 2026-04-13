import { useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { CheckCircle2, FileCheck2, LockKeyhole, UploadCloud } from 'lucide-react'
import { useSessionQuery } from '@/entities/auth/queries'
import { hasRequiredInternalEmail } from '@/app/config/routes'
import type { VisibilityScope } from '@/entities/documents/types'
import { useFileUploadMutation, useTextUploadMutation, useUrlUploadMutation } from '@/entities/submissions/queries'
import type { UploadSourceType } from '@/entities/submissions/types'
import { parseTagInput, validateUploadDraft, type UploadDraftFormValues } from '@/features/uploads/schema'
import { formatDateTime } from '@/shared/lib/format'
import {
    Badge,
    Button,
    Card,
    Checkbox,
    FileDropzone,
    Input,
    Select,
    Tabs,
    TabsContent,
    TabsList,
    TabsTrigger,
    Textarea,
} from '@/shared/ui'

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
    { value: 'internal', label: 'Chỉ nội bộ' },
    { value: 'public', label: 'Công khai sau duyệt' },
] satisfies Array<{ value: VisibilityScope; label: string }>

const sourceHints: Record<UploadSourceType, { title: string; description: string }> = {
    file: {
        title: 'Tệp chính thức',
        description: 'Dùng cho PDF, DOCX hoặc văn bản đã có file gốc.',
    },
    text: {
        title: 'Nội dung văn bản',
        description: 'Dán trực tiếp thông báo nếu chưa nhận được file chính thức.',
    },
    url: {
        title: 'Liên kết nguồn',
        description: 'Gắn link trang UIT hoặc đơn vị trực thuộc đang lưu bản gốc.',
    },
}

export function UploadWorkspace({ scenario }: { scenario?: string }) {
    const sessionQuery = useSessionQuery({ scenario })
    const [files, setFiles] = useState<File[]>([])
    const [progressValue, setProgressValue] = useState(0)
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

    useEffect(() => {
        if (!isSubmitting) {
            setProgressValue(latestSubmission ? 100 : 0)
            return
        }

        setProgressValue((current) => (current > 6 ? current : 12))
        const timer = window.setInterval(() => {
            setProgressValue((current) => (current >= 92 ? current : current + 8))
        }, 220)

        return () => window.clearInterval(timer)
    }, [isSubmitting, latestSubmission])

    const sourceReady =
        sourceType === 'file' ? files.length > 0 : sourceType === 'text' ? rawText.trim().length >= 80 : Boolean(url.trim())
    const readinessScore = [Boolean(title.trim()), sourceReady, Boolean(issuingUnit.trim()), confirmOwnership, confirmReviewReady].filter(Boolean).length
    const uploader = sessionQuery.data?.user
    const isUitAccount = uploader ? hasRequiredInternalEmail(uploader.role, uploader.email) : false
    const currentSourceHint = sourceHints[sourceType]

    const checklist = useMemo(
        () => [
            { label: 'Nguồn tài liệu', done: sourceReady },
            { label: 'Tiêu đề', done: Boolean(title.trim()) },
            { label: 'Đơn vị ban hành', done: Boolean(issuingUnit.trim()) },
            { label: 'Xác nhận quyền sở hữu', done: confirmOwnership },
            { label: 'Sẵn sàng cho hàng duyệt', done: confirmReviewReady },
        ],
        [confirmOwnership, confirmReviewReady, issuingUnit, sourceReady, title],
    )

    const resetDraft = () => {
        reset(defaultValues)
        setFiles([])
        setProgressValue(0)
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
            tags: parseTagInput(values.tagsInput),
            notes: result.data.notes,
        }

        try {
            if (result.data.sourceType === 'file') {
                const selectedFile = files[0]
                await fileUpload.mutateAsync({
                    ...basePayload,
                    file: selectedFile,
                    fileName: selectedFile?.name,
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
            // Mutation state already surfaces the error.
        }
    })

    return (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
            <Card className="space-y-6">
                <div className="grid gap-4 lg:grid-cols-2">
                    <div className="rounded-[1.5rem] border border-gray-200 bg-white/88 p-4 dark:border-gray-800 dark:bg-[#101a2c]">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">Người tải lên</div>
                        <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                            {uploader ? `${uploader.name} · ${uploader.email}` : 'Đang kiểm tra phiên đăng nhập...'}
                        </p>
                        {uploader ? (
                            <p className="mt-1 text-xs text-gray-500">
                                {isUitAccount
                                    ? 'Email trường hợp lệ cho role hiện tại.'
                                    : 'Role này yêu cầu đăng nhập Google bằng email trường @gm.uit.edu.vn.'}
                            </p>
                        ) : null}
                    </div>

                    <div className="rounded-[1.5rem] border border-brand-200 bg-brand-50/80 p-4 dark:border-brand-900 dark:bg-brand-950/35">
                        <div className="flex items-center gap-2 text-sm font-semibold text-brand-800 dark:text-brand-200">
                            <LockKeyhole size={16} />
                            Chính sách tải nội bộ
                        </div>
                        <p className="mt-2 text-sm leading-6 text-brand-700 dark:text-brand-300">
                            Teacher và admin phải đăng nhập bằng Google Workspace UIT với email đuôi `@gm.uit.edu.vn`, sau đó tài liệu mới đi vào hàng duyệt.
                        </p>
                    </div>
                </div>

                <form className="space-y-6" onSubmit={(event) => void submitDraft(event)}>
                    <input type="hidden" {...register('fileCount', { valueAsNumber: true })} />
                    <input type="hidden" {...register('tagsInput')} />

                    <div className="space-y-2">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">Nguồn nộp tài liệu</div>
                        <p className="text-sm text-gray-500">{currentSourceHint.description}</p>
                    </div>

                    <Tabs
                        value={sourceType}
                        onValueChange={(value) => {
                            setValue('sourceType', value as UploadSourceType, { shouldDirty: true })
                            clearErrors(['fileCount', 'rawText', 'url'])
                        }}
                    >
                        <TabsList>
                            <TabsTrigger value="file">Tệp</TabsTrigger>
                            <TabsTrigger value="text">Văn bản</TabsTrigger>
                            <TabsTrigger value="url">Liên kết</TabsTrigger>
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
                                label="Nội dung văn bản"
                                placeholder="Dán nguyên văn thông báo, quyết định hoặc phần mô tả chính cần đưa vào hàng duyệt..."
                                error={errors.rawText?.message}
                                {...register('rawText')}
                            />
                        </TabsContent>

                        <TabsContent value="url">
                            <Input
                                label="Liên kết nguồn"
                                placeholder="https://gm.uit.edu.vn/..."
                                error={errors.url?.message}
                                {...register('url')}
                            />
                        </TabsContent>
                    </Tabs>

                    <div className="grid gap-4 md:grid-cols-2">
                        <Input
                            label="Tiêu đề tài liệu"
                            placeholder="Ví dụ: Thông báo học phí học kỳ 2"
                            error={errors.title?.message}
                            {...register('title')}
                        />
                        <Input
                            label="Đơn vị ban hành"
                            placeholder="Ví dụ: Phòng Đào tạo Đại học"
                            error={errors.issuingUnit?.message}
                            {...register('issuingUnit')}
                        />
                    </div>

                    <div className="grid gap-4 md:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
                        <Select
                            label="Phạm vi hiển thị"
                            options={visibilityOptions}
                            error={errors.visibilityScope?.message}
                            value={visibilityScope}
                            {...register('visibilityScope')}
                        />
                        <Textarea
                            label="Ghi chú cho người duyệt"
                            placeholder="Thêm bối cảnh ngắn gọn nếu tài liệu cần ưu tiên, cần rà ngày hiệu lực hoặc cần công khai cho sinh viên."
                            error={errors.notes?.message}
                            {...register('notes')}
                        />
                    </div>

                    <div className="space-y-3 rounded-[1.5rem] border border-gray-200 bg-white/88 p-4 dark:border-gray-800 dark:bg-[#101a2c]">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">Xác nhận trước khi gửi</div>
                        <Checkbox
                            label="Đây là nguồn chính thức của UIT hoặc đơn vị trực thuộc."
                            hint="Bắt buộc để tài liệu đi vào hàng duyệt."
                            checked={confirmOwnership}
                            onChange={(event) => {
                                setValue('confirmOwnership', event.target.checked, { shouldDirty: true })
                                clearErrors('confirmOwnership')
                            }}
                        />
                        {errors.confirmOwnership ? <p className="text-xs font-medium text-error-600">{errors.confirmOwnership.message}</p> : null}

                        <Checkbox
                            label="Tài liệu đã sẵn sàng để admin rà soát."
                            hint="Tiêu đề, nguồn và đơn vị ban hành cần rõ ràng trước khi gửi."
                            checked={confirmReviewReady}
                            onChange={(event) => {
                                setValue('confirmReviewReady', event.target.checked, { shouldDirty: true })
                                clearErrors('confirmReviewReady')
                            }}
                        />
                        {errors.confirmReviewReady ? <p className="text-xs font-medium text-error-600">{errors.confirmReviewReady.message}</p> : null}
                    </div>

                    {uploadError ? (
                        <div className="rounded-2xl border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-700 dark:border-error-900 dark:bg-error-950/40 dark:text-error-200">
                            {uploadError.message}
                        </div>
                    ) : null}

                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <Button type="button" variant="secondary" onClick={resetDraft}>
                            Xóa nháp
                        </Button>
                        <Button type="submit" isLoading={isSubmitting}>
                            <UploadCloud size={16} />
                            Gửi tài liệu
                        </Button>
                    </div>
                </form>
            </Card>

            <div className="space-y-4">
                <Card className="space-y-4">
                    <div className="flex items-center justify-between gap-3">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">Tiến độ xử lý</div>
                        <Badge tone={readinessScore >= 4 ? 'success' : readinessScore >= 2 ? 'warning' : 'neutral'}>
                            Sẵn sàng {readinessScore}/5
                        </Badge>
                    </div>

                    <div className="space-y-2">
                        <div className="h-3 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
                            <div
                                className="h-full rounded-full bg-brand-600 transition-all duration-300"
                                style={{ width: `${progressValue}%` }}
                            />
                        </div>
                        <div className="flex items-center justify-between text-xs text-gray-500">
                            <span>{isSubmitting ? 'Đang gửi lên hàng duyệt...' : latestSubmission ? 'Đã tạo phiếu nộp' : currentSourceHint.title}</span>
                            <span>{progressValue}%</span>
                        </div>
                    </div>

                    <div className="space-y-2">
                        {checklist.map((item) => (
                            <div key={item.label} className="flex items-center justify-between gap-3 text-sm">
                                <span className="text-gray-600 dark:text-gray-300">{item.label}</span>
                                <Badge tone={item.done ? 'success' : 'neutral'}>{item.done ? 'Đạt' : 'Chờ'}</Badge>
                            </div>
                        ))}
                    </div>
                </Card>

                <Card className="space-y-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                        <FileCheck2 size={16} className="text-brand-600" />
                        Trạng thái gần nhất
                    </div>

                    {latestSubmission ? (
                        <div className="space-y-4 text-sm text-gray-600 dark:text-gray-300">
                            <div className="rounded-[1.5rem] border border-success-200 bg-success-50/90 p-4 dark:border-success-900 dark:bg-success-950/25">
                                <div className="flex items-center gap-2 font-semibold text-success-700 dark:text-success-300">
                                    <CheckCircle2 size={16} />
                                    Đã tạo phiếu nộp
                                </div>
                                <div className="mt-2 text-sm leading-6 text-success-700 dark:text-success-300">{latestSubmission.title}</div>
                            </div>

                            <div className="space-y-2">
                                <div className="flex items-center justify-between gap-3">
                                    <span>Mã phiếu</span>
                                    <span className="font-medium text-gray-900 dark:text-white">{latestSubmission.id}</span>
                                </div>
                                <div className="flex items-center justify-between gap-3">
                                    <span>Xử lý</span>
                                    <span className="font-medium capitalize text-gray-900 dark:text-white">{latestSubmission.processingStatus}</span>
                                </div>
                                <div className="flex items-center justify-between gap-3">
                                    <span>Hàng duyệt</span>
                                    <span className="font-medium capitalize text-gray-900 dark:text-white">{latestSubmission.lifecycleStatus.replace('_', ' ')}</span>
                                </div>
                                <div className="flex items-center justify-between gap-3">
                                    <span>Cập nhật</span>
                                    <span className="font-medium text-gray-900 dark:text-white">{formatDateTime(latestSubmission.updatedAt)}</span>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-2 text-sm leading-6 text-gray-500">
                            <p>1. Chọn đúng nguồn nộp.</p>
                            <p>2. Điền tiêu đề và đơn vị ban hành.</p>
                            <p>3. Xác nhận rồi gửi vào hàng duyệt.</p>
                        </div>
                    )}
                </Card>
            </div>
        </div>
    )
}
