import type { SelectHTMLAttributes } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/shared/lib/cn'

export interface SelectOption {
    label: string
    value: string
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
    label?: string
    hint?: string
    error?: string
    options: SelectOption[]
}

export function Select({ className, label, hint, error, options, id, ...props }: SelectProps) {
    const fieldId = id ?? label?.toLowerCase().replace(/\s+/g, '-')

    return (
        <label className="flex w-full flex-col gap-1.5" htmlFor={fieldId}>
            {label ? <span className="text-sm font-medium text-gray-700 dark:text-gray-200">{label}</span> : null}
            <div className="relative">
                <select
                    id={fieldId}
                    className={cn(
                        'w-full appearance-none rounded-xl border border-gray-200 bg-white px-4 py-2.5 pr-10 text-sm text-gray-900 outline-none transition focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white',
                        error && 'border-error-500 focus:border-error-500 focus:ring-error-500/10',
                        className,
                    )}
                    {...props}
                >
                    {options.map((option) => (
                        <option key={option.value} value={option.value}>
                            {option.label}
                        </option>
                    ))}
                </select>
                <ChevronDown size={16} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" />
            </div>
            {error ? <span className="text-xs font-medium text-error-600">{error}</span> : null}
            {!error && hint ? <span className="text-xs text-gray-500">{hint}</span> : null}
        </label>
    )
}
