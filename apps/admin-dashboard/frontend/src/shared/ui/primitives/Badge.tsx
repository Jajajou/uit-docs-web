import type { HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/shared/lib/cn'

const badgeVariants = cva('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold', {
    variants: {
        tone: {
            neutral: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-200',
            brand: 'bg-brand-100 text-brand-700 dark:bg-brand-950 dark:text-brand-200',
            success: 'bg-success-50 text-success-700 dark:bg-success-950 dark:text-success-300',
            warning: 'bg-warning-50 text-warning-700 dark:bg-warning-950 dark:text-warning-300',
            danger: 'bg-error-50 text-error-700 dark:bg-error-950 dark:text-error-300',
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
