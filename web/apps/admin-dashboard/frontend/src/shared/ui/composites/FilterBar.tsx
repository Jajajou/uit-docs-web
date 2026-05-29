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
        <Card className="relative z-20 gap-4 border-white/70 bg-white/84 p-4 dark:border-brand-400/12 dark:bg-[linear-gradient(180deg,rgba(7,15,28,0.92),rgba(10,22,40,0.95))]">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
                <div className="relative min-w-0">
                    <Input
                        aria-label="Search"
                        value={searchValue}
                        onChange={(event) => onSearchChange(event.target.value)}
                        placeholder={searchPlaceholder}
                        className="h-12 rounded-[1.4rem] border-white/80 bg-white/96 pl-11 shadow-none dark:border-brand-400/16 dark:bg-[rgba(9,20,36,0.92)] dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:border-brand-300 dark:focus:ring-brand-500/18"
                    />
                    <Search size={18} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 dark:text-slate-400" />
                </div>
                {actions ? <div className="flex flex-wrap gap-3 xl:justify-end">{actions}</div> : null}
            </div>
        </Card>
    )
}
