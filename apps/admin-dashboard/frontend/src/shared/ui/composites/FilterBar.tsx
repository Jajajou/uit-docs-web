import type { ReactNode } from 'react'
import { Search } from 'lucide-react'
import { Card } from '@/shared/ui/primitives/Card'
import { Input } from '@/shared/ui/primitives/Input'

interface FilterBarProps {
    searchValue: string
    onSearchChange: (value: string) => void
    searchPlaceholder?: string
    actions?: ReactNode
}

export function FilterBar({
    searchValue,
    onSearchChange,
    searchPlaceholder = 'Search...',
    actions,
}: FilterBarProps) {
    return (
        <Card className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex-1">
                <Input
                    aria-label="Search"
                    value={searchValue}
                    onChange={(event) => onSearchChange(event.target.value)}
                    placeholder={searchPlaceholder}
                    className="pl-10"
                />
                <Search size={18} className="pointer-events-none relative -top-9 left-3.5 text-gray-400" />
            </div>
            {actions ? <div className="flex flex-wrap gap-3">{actions}</div> : null}
        </Card>
    )
}
