import type { HTMLAttributes, TableHTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from 'react'
import { cn } from '@/shared/lib/cn'

export function Table({ className, ...props }: TableHTMLAttributes<HTMLTableElement>) {
    return <table className={cn('w-full border-collapse', className)} {...props} />
}

export function TableHead({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
    return <thead className={cn('bg-gray-50 dark:bg-gray-800/50', className)} {...props} />
}

export function TableBody({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
    return <tbody className={cn('[&_tr:last-child_td]:border-b-0', className)} {...props} />
}

export function TableRow({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
    return <tr className={cn('border-b border-gray-200 dark:border-gray-800', className)} {...props} />
}

export function TableHeaderCell({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
    return (
        <th
            className={cn('px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400', className)}
            {...props}
        />
    )
}

export function TableCell({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
    return <td className={cn('px-4 py-3 text-sm text-gray-700 dark:text-gray-200', className)} {...props} />
}
