import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Outlet, useLocation } from 'react-router-dom'
import { publicNavItems } from '@/app/config/routes'
import { RouteIntentLink } from '@/app/router/RouteIntentLink'
import { scheduleIdleTask } from '@/app/router/routeModules'
import { useRouteWarmup } from '@/app/router/useRouteWarmup'
import { prefetchConversationsQuery } from '@/entities/chat/queries'
import { RoleSwitcher } from '@/features/auth/RoleSwitcher'

export default function PublicLayout() {
    const location = useLocation()
    const queryClient = useQueryClient()

    useRouteWarmup('/chat')

    useEffect(() => {
        if (location.pathname === '/chat') {
            return undefined
        }

        return scheduleIdleTask(() => {
            void prefetchConversationsQuery(queryClient)
        })
    }, [location.pathname, queryClient])

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
            <header className="border-b border-gray-200 bg-white/95 px-4 py-4 backdrop-blur dark:border-gray-800 dark:bg-gray-950/95">
                <div className="mx-auto flex max-w-7xl flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <div className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-600">UIT portal</div>
                        <div className="text-lg font-bold text-gray-950 dark:text-white">Public shell</div>
                    </div>
                    <nav className="flex flex-wrap gap-2">
                        {publicNavItems.map((item) => (
                            <RouteIntentLink
                                key={item.path}
                                to={item.path}
                                className="rounded-xl border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-200 dark:hover:bg-gray-900"
                            >
                                {item.label}
                            </RouteIntentLink>
                        ))}
                    </nav>
                    <div className="flex flex-wrap items-center gap-3">
                        <RoleSwitcher />
                        <RouteIntentLink
                            to="/auth/login"
                            className="rounded-xl border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-200 dark:hover:bg-gray-900"
                        >
                            Auth
                        </RouteIntentLink>
                    </div>
                </div>
            </header>

            <main className="mx-auto max-w-7xl px-4 py-6 md:px-6">
                <Outlet />
            </main>
        </div>
    )
}
