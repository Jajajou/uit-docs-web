import { Outlet, useLocation } from 'react-router-dom'
import { canAccessPath, getRouteMeta, type AppShellKind } from '@/app/config/routes'
import { RouteIntentLink } from '@/app/router/RouteIntentLink'
import { triggerRouteIntentPrefetch } from '@/app/router/routePrefetch'
import { RoleSwitcher } from '@/features/auth/RoleSwitcher'
import { useSessionStore } from '@/entities/auth/store'
import type { SidebarNavItem } from '@/shared/ui/composites/Sidebar'
import { Sidebar, Topbar } from '@/shared/ui/composites'

interface AppShellFrameProps {
    shellKind: AppShellKind
    sidebarTitle: string
    sidebarSubtitle: string
    navItems: SidebarNavItem[]
}

export function AppShellFrame({
    shellKind,
    sidebarTitle,
    sidebarSubtitle,
    navItems,
}: AppShellFrameProps) {
    const location = useLocation()
    const selectedRole = useSessionStore((state) => state.selectedRole)
    const currentRoute = getRouteMeta(location.pathname)
    const accessibleNavItems = navItems.filter((item) => canAccessPath(selectedRole, item.path))
    const sidebarItems = accessibleNavItems.map((item) => ({
        ...item,
        onIntentPrefetch: () => triggerRouteIntentPrefetch(item.path),
    }))

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-950 lg:grid lg:grid-cols-[18rem_1fr]">
            <div className="hidden lg:block">
                <Sidebar title={sidebarTitle} subtitle={sidebarSubtitle} items={sidebarItems} />
            </div>

            <div className="flex min-h-screen flex-col">
                <Topbar
                    title={currentRoute?.title ?? 'Foundation shell'}
                    breadcrumbs={[
                        { label: shellKind.toUpperCase() },
                        { label: currentRoute?.title ?? 'Unknown route' },
                    ]}
                    roleSwitcher={<RoleSwitcher />}
                />

                <div className="border-b border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-950 lg:hidden">
                    <div className="flex gap-2 overflow-x-auto">
                        {accessibleNavItems.map((item) => (
                            <RouteIntentLink
                                key={item.path}
                                to={item.path}
                                className="whitespace-nowrap rounded-xl border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 dark:border-gray-800 dark:text-gray-200"
                            >
                                {item.label}
                            </RouteIntentLink>
                        ))}
                    </div>
                </div>

                <main className="flex-1 px-4 py-6 md:px-6">
                    <Outlet />
                </main>
            </div>
        </div>
    )
}
