import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '@/shared/lib/cn'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
    label?: string
    hint?: string
    error?: string
}

const inputBaseClassName =
    'w-full rounded-2xl border border-gray-200 bg-white/92 px-4 py-3 text-sm text-gray-900 shadow-theme-xs outline-none transition-all duration-200 placeholder:text-gray-400 focus:border-brand-400 focus:ring-4 focus:ring-brand-500/12 dark:border-gray-700 dark:bg-[#111c2d] dark:text-white dark:placeholder:text-gray-500 dark:focus:border-brand-500'

export const Input = forwardRef<HTMLInputElement, InputProps>(
    ({ className, label, hint, error, id, ...props }, ref) => {
        const fieldId = id ?? label?.toLowerCase().replace(/\s+/g, '-')

        return (
            <label className="flex w-full flex-col gap-1.5" htmlFor={fieldId}>
                {label ? <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">{label}</span> : null}
                <input
                    ref={ref}
                    id={fieldId}
                    className={cn(inputBaseClassName, error && 'border-error-500 focus:border-error-500 focus:ring-error-500/10', className)}
                    {...props}
                />
                {error ? <span className="text-xs font-medium text-error-600">{error}</span> : null}
                {!error && hint ? <span className="text-xs text-gray-500">{hint}</span> : null}
            </label>
        )
    },
)

Input.displayName = 'Input'
