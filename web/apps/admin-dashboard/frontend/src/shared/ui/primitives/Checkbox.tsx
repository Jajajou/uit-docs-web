import type { InputHTMLAttributes } from 'react'
import { cn } from '@/shared/lib/cn'

export interface CheckboxProps extends InputHTMLAttributes<HTMLInputElement> {
    label: string
    hint?: string
}

export function Checkbox({ className, label, hint, id, ...props }: CheckboxProps) {
    const fieldId = id ?? label.toLowerCase().replace(/\s+/g, '-')

    return (
        <label htmlFor={fieldId} className="flex items-start gap-3">
            <input
                id={fieldId}
                type="checkbox"
                className={cn(
                    'mt-1 h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500/30 dark:border-gray-700 dark:bg-[#111c2d]',
                    className,
                )}
                {...props}
            />
            <span className="flex flex-col gap-1">
                <span className="text-sm font-semibold text-gray-800 dark:text-gray-100">{label}</span>
                {hint ? <span className="text-xs text-gray-500">{hint}</span> : null}
            </span>
        </label>
    )
}
