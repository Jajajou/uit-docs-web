import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/shared/lib/cn'

interface PageHeaderProps {
    title: string
    description?: string
    icon?: LucideIcon
    actions?: ReactNode
    className?: string
}

export function PageHeader({ title, description, icon: Icon, actions, className }: PageHeaderProps) {
    return (
        <div className={cn('flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between', className)}>
            <div className="flex items-start gap-4">
                {Icon ? (
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-200">
                        <Icon size={24} />
                    </div>
                ) : null}
                <div className="space-y-1">
                    <h1 className="text-2xl font-bold tracking-tight text-gray-950 dark:text-white">{title}</h1>
                    {description ? <p className="max-w-2xl text-sm text-gray-500">{description}</p> : null}
                </div>
            </div>
            {actions ? <div className="flex flex-wrap gap-3">{actions}</div> : null}
        </div>
    )
}
