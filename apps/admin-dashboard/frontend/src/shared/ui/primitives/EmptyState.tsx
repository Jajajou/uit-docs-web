import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { Card } from '@/shared/ui/primitives/Card'

interface EmptyStateProps {
    icon: LucideIcon
    title: string
    description: string
    action?: ReactNode
}

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
    return (
        <Card className="flex min-h-72 flex-col items-center justify-center gap-4 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-300">
                <Icon size={24} />
            </div>
            <div className="space-y-1">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h3>
                <p className="max-w-md text-sm text-gray-500">{description}</p>
            </div>
            {action}
        </Card>
    )
}
