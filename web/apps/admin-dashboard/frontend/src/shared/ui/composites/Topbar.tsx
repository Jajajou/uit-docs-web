import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/shared/ui/primitives/Badge'

interface TopbarProps {
    title: string
    breadcrumbs: Array<{ label: string; href?: string }>
    actions?: ReactNode
    roleSwitcher?: ReactNode
}

export function Topbar({ title, breadcrumbs, actions, roleSwitcher }: TopbarProps) {
    return (
        <header className="sticky top-0 z-20 border-b border-gray-200 bg-white/95 px-6 py-4 backdrop-blur dark:border-gray-800 dark:bg-gray-950/95">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
                        {breadcrumbs.map((crumb, index) => (
                            <span key={`${crumb.label}-${index}`} className="flex items-center gap-2">
                                {crumb.href ? <Link to={crumb.href} className="hover:text-gray-900 dark:hover:text-white">{crumb.label}</Link> : <span>{crumb.label}</span>}
                                {index < breadcrumbs.length - 1 ? <span>/</span> : null}
                            </span>
                        ))}
                    </div>
                    <div className="flex items-center gap-3">
                        <h2 className="text-xl font-bold text-gray-950 dark:text-white">{title}</h2>
                        <Badge tone="brand">Foundation mode</Badge>
                    </div>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                    {roleSwitcher}
                    {actions}
                </div>
            </div>
        </header>
    )
}
