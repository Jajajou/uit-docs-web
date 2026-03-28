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
                'rounded-2xl border-2 border-dashed border-gray-300 bg-gray-50 p-8 text-center transition hover:border-brand-400 hover:bg-brand-50/50 dark:border-gray-700 dark:bg-gray-900 dark:hover:border-brand-500 dark:hover:bg-brand-950',
                isDragActive && 'border-brand-500 bg-brand-50 dark:bg-brand-950',
            )}
        >
            <input {...getInputProps()} />
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-brand-600 shadow-theme-sm dark:bg-gray-950">
                <UploadCloud size={24} />
            </div>
            <div className="mt-4 space-y-1">
                <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                    {isDragActive ? 'Drop files to upload' : 'Upload files or drag them here'}
                </h3>
                <p className="text-sm text-gray-500">Max file size: {formatFileSize(maxSize)}</p>
            </div>
            {value.length > 0 ? (
                <div className="mt-6 space-y-2 text-left">
                    {value.map((file) => (
                        <div
                            key={`${file.name}-${file.lastModified}`}
                            className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm dark:border-gray-800 dark:bg-gray-950"
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
