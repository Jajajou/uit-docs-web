import type { ReactNode } from 'react'
import { Card } from '@/shared/ui/primitives/Card'
import { MetadataField } from '@/shared/ui/primitives/MetadataField'

interface MetadataPanelProps {
    title: string
    entries: Array<{
        label: string
        value: ReactNode
        hint?: string
    }>
}

export function MetadataPanel({ title, entries }: MetadataPanelProps) {
    return (
        <Card className="space-y-4">
            <div className="text-base font-semibold text-gray-900 dark:text-white">{title}</div>
            <div className="grid gap-3 md:grid-cols-2">
                {entries.map((entry) => (
                    <MetadataField key={entry.label} label={entry.label} value={entry.value} hint={entry.hint} />
                ))}
            </div>
        </Card>
    )
}
