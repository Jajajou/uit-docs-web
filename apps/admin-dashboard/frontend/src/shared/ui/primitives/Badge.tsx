import type { HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/shared/lib/cn'

const badgeVariants = cva('inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold', {
    variants: {
        tone: {
            neutral: 'border-gray-200 bg-white/90 text-gray-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200',
            brand: 'border-brand-200 bg-brand-50/90 text-brand-700 dark:border-brand-800 dark:bg-brand-950/70 dark:text-brand-200',
            success: 'border-success-300 bg-success-50/90 text-success-700 dark:border-success-900 dark:bg-success-950/60 dark:text-success-300',
            warning: 'border-warning-200 bg-warning-50/90 text-warning-700 dark:border-warning-900 dark:bg-warning-950/60 dark:text-warning-300',
            danger: 'border-error-200 bg-error-50/90 text-error-700 dark:border-error-900 dark:bg-error-950/60 dark:text-error-300',
            purple: 'border-purple-200 bg-purple-50/90 text-purple-700 dark:border-purple-900 dark:bg-purple-950/60 dark:text-purple-300',
        },
    },
    defaultVariants: {
        tone: 'neutral',
    },
})

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
    return <span className={cn(badgeVariants({ tone }), className)} {...props} />
}
