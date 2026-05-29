import type { HTMLAttributes } from 'react'
import { cn } from '@/shared/lib/cn'

export type SkeletonProps = HTMLAttributes<HTMLDivElement>

export function Skeleton({ className, ...props }: SkeletonProps) {
    return <div className={cn('animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800', className)} {...props} />
}
