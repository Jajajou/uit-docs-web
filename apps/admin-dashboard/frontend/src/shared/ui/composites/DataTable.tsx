import type { ReactNode } from 'react'
import { EmptyState } from '@/shared/ui/primitives/EmptyState'
import { Skeleton } from '@/shared/ui/primitives/Skeleton'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeaderCell,
    TableRow,
} from '@/shared/ui/primitives/Table'
import { Card } from '@/shared/ui/primitives/Card'
import type { LucideIcon } from 'lucide-react'

export interface DataTableColumn<TData> {
    key: string
    header: string
    render: (row: TData) => ReactNode
    className?: string
}

interface DataTableProps<TData> {
    rows: TData[]
    columns: DataTableColumn<TData>[]
    isLoading?: boolean
    getRowKey?: (row: TData, index: number) => string
    emptyIcon: LucideIcon
    emptyTitle: string
    emptyDescription: string
}

export function DataTable<TData>({
    rows,
    columns,
    isLoading,
    getRowKey,
    emptyIcon,
    emptyTitle,
    emptyDescription,
}: DataTableProps<TData>) {
    if (isLoading) {
        return (
            <Card className="space-y-3">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
            </Card>
        )
    }

    if (rows.length === 0) {
        return <EmptyState icon={emptyIcon} title={emptyTitle} description={emptyDescription} />
    }

    return (
        <Card className="overflow-hidden p-0">
            <div className="overflow-x-auto">
                <Table>
                    <TableHead>
                        <TableRow>
                            {columns.map((column) => (
                                <TableHeaderCell key={column.key} className={column.className}>
                                    {column.header}
                                </TableHeaderCell>
                            ))}
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {rows.map((row, index) => (
                            <TableRow key={getRowKey ? getRowKey(row, index) : String(index)}>
                                {columns.map((column) => (
                                    <TableCell key={column.key} className={column.className}>
                                        {column.render(row)}
                                    </TableCell>
                                ))}
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>
        </Card>
    )
}
