import { NavLink } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/shared/lib/cn'

export interface SidebarNavItem {
    label: string
    path: string
    icon: LucideIcon
    onIntentPrefetch?: () => void
}

interface SidebarProps {
    title: string
    subtitle: string
    items: SidebarNavItem[]
}

export function Sidebar({ title, subtitle, items }: SidebarProps) {
    return (
        <aside className="flex h-screen w-72 flex-col border-r border-gray-200 bg-white px-4 py-6 dark:border-gray-800 dark:bg-gray-950">
            <div className="px-3">
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-600">{subtitle}</div>
                <div className="mt-1 text-xl font-bold text-gray-950 dark:text-white">{title}</div>
            </div>
            <nav className="mt-8 flex-1 space-y-1">
                {items.map((item) => {
                    const Icon = item.icon

                    return (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            onMouseEnter={item.onIntentPrefetch}
                            onFocus={item.onIntentPrefetch}
                            onTouchStart={item.onIntentPrefetch}
                            className={({ isActive }) =>
                                cn(
                                    'flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-gray-600 transition hover:bg-gray-100 hover:text-gray-950 dark:text-gray-300 dark:hover:bg-gray-900 dark:hover:text-white',
                                    isActive && 'bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-200',
                                )
                            }
                        >
                            <Icon size={18} />
                            <span>{item.label}</span>
                        </NavLink>
                    )
                })}
            </nav>
        </aside>
    )
}
