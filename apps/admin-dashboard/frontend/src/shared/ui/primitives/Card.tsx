import type { HTMLAttributes } from 'react'
import { cn } from '@/shared/lib/cn'

export type CardProps = HTMLAttributes<HTMLDivElement>

export function Card({ className, ...props }: CardProps) {
    return (
        <div
            className={cn(
                'rounded-2xl border border-gray-200 bg-white p-5 shadow-theme-sm dark:border-gray-800 dark:bg-gray-900',
                className,
            )}
            {...props}
        />
    )
}
