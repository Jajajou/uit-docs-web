import { useCallback } from 'react'
import { UploadCloud } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { cn } from '@/shared/lib/cn'
import { formatFileSize } from '@/shared/lib/format'

interface FileDropzoneProps {
    value: File[]
    onChange: (files: File[]) => void
    accept?: Record<string, string[]>
    maxSize?: number
}

export function FileDropzone({ value, onChange, accept, maxSize = 50 * 1024 * 1024 }: FileDropzoneProps) {
    const onDrop = useCallback(
        (files: File[]) => {
            onChange([...value, ...files])
        },
        [onChange, value],
    )

    const { getInputProps, getRootProps, isDragActive } = useDropzone({
        onDrop,
        accept,
        maxSize,
        multiple: true,
    })

    return (
        <div
            {...getRootProps()}
            className={cn(
                'rounded-[1.75rem] border-2 border-dashed border-gray-300 bg-gradient-to-br from-white to-brand-50/60 p-8 text-center transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-400 hover:from-white hover:to-brand-100/80 hover:shadow-theme-md dark:border-gray-700 dark:bg-gradient-to-br dark:from-[#111c2d] dark:to-[#16253d] dark:hover:border-brand-500 dark:hover:shadow-theme-lg',
                isDragActive && 'border-brand-500 from-brand-50 to-brand-100 dark:from-[#122a52] dark:to-[#16315b]',
            )}
        >
            <input {...getInputProps()} />
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-brand-600 shadow-theme-sm dark:bg-[#0f172a]">
                <UploadCloud size={24} />
            </div>
            <div className="mt-4 space-y-1">
                <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                    {isDragActive ? 'Thả tệp để tải lên' : 'Kéo tệp vào đây hoặc bấm để chọn'}
                </h3>
                <p className="text-sm text-gray-500">Dung lượng tối đa mỗi tệp: {formatFileSize(maxSize)}</p>
            </div>
            {value.length > 0 ? (
                <div className="mt-6 space-y-2 text-left">
                    {value.map((file) => (
                        <div
                            key={`${file.name}-${file.lastModified}`}
                            className="flex items-center justify-between rounded-2xl border border-gray-200 bg-white/95 px-4 py-3 text-sm dark:border-gray-800 dark:bg-[#0f172a]/95"
                        >
                            <span className="truncate text-gray-900 dark:text-white">{file.name}</span>
                            <span className="text-gray-500">{formatFileSize(file.size)}</span>
                        </div>
                    ))}
                </div>
            ) : null}
        </div>
    )
}
