import type { HTMLAttributes } from 'react'
import { cn } from '@/shared/lib/cn'

export type CardProps = HTMLAttributes<HTMLDivElement>

export function Card({ className, ...props }: CardProps) {
    return (
        <div
            className={cn(
                'rounded-[1.75rem] border border-white/70 bg-white/88 p-5 shadow-theme-sm backdrop-blur-sm dark:border-[#214263]/80 dark:bg-[linear-gradient(180deg,rgba(8,18,30,0.92),rgba(13,29,48,0.9))] dark:shadow-[0_22px_60px_rgba(2,8,23,0.42)]',
                className,
            )}
            {...props}
        />
    )
}
