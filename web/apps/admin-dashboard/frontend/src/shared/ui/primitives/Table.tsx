import type { HTMLAttributes, TableHTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from 'react'
import { cn } from '@/shared/lib/cn'

export function Table({ className, ...props }: TableHTMLAttributes<HTMLTableElement>) {
    return <table className={cn('min-w-full border-collapse', className)} {...props} />
}

export function TableHead({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
    return (
        <thead
            className={cn(
                'bg-[linear-gradient(180deg,rgba(248,250,252,0.92),rgba(241,245,249,0.92))] dark:bg-[linear-gradient(180deg,rgba(12,24,41,0.98),rgba(9,18,31,0.96))]',
                className,
            )}
            {...props}
        />
    )
}

export function TableBody({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
    return (
        <tbody
            className={cn(
                '[&_tr:last-child_td]:border-b-0 [&_tr:nth-child(even)]:bg-gray-50/85 dark:[&_tr:nth-child(even)]:bg-brand-500/[0.04]',
                className,
            )}
            {...props}
        />
    )
}

export function TableRow({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
    return (
        <tr
            className={cn(
                'border-b border-gray-200/90 transition-colors hover:bg-brand-50/55 dark:border-brand-400/10 dark:hover:bg-brand-500/[0.08]',
                className,
            )}
            {...props}
        />
    )
}

export function TableHeaderCell({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
    return (
        <th
            className={cn(
                'px-4 py-3.5 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-500 dark:text-slate-300',
                className,
            )}
            {...props}
        />
    )
}

export function TableCell({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
    return <td className={cn('px-4 py-3.5 text-sm text-gray-700 dark:text-slate-100', className)} {...props} />
}
