import type { ReactNode } from 'react'
import { Card } from '@/shared/ui/primitives/Card'

interface MetadataFieldProps {
    label: string
    value: ReactNode
    hint?: string
}

export function MetadataField({ label, value, hint }: MetadataFieldProps) {
    return (
        <Card className="space-y-1 border-gray-100 p-4 shadow-none dark:border-gray-800">
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</div>
            <div className="text-sm font-medium text-gray-900 dark:text-white">{value || 'Not available'}</div>
            {hint ? <div className="text-xs text-gray-500">{hint}</div> : null}
        </Card>
    )
}
