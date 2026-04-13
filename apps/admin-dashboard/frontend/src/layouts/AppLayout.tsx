import { AnimatePresence, motion } from 'framer-motion'
import { LogOut, Moon, Sun } from 'lucide-react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { canAccessPath, getExperienceRoleLabel } from '@/app/config/routes'
import { RouteIntentLink } from '@/app/router/RouteIntentLink'
import { useLogoutSessionMutation, useSessionQuery } from '@/entities/auth/queries'
import { useSessionStore } from '@/entities/auth/store'
import { useThemeStore } from '@/entities/preferences/theme'
import { cn } from '@/shared/lib/cn'
import { useScenarioParam } from '@/shared/lib/scenario'
import { Badge, Button } from '@/shared/ui'

const workspaceNav = [
    { path: '/chat', label: 'Chat' },
    { path: '/upload', label: 'Tải lên' },
    { path: '/manager', label: 'Quản trị' },
]

function isChatRoute(pathname: string) {
    return pathname === '/' || pathname === '/chat' || pathname.startsWith('/documents/')
}

export default function AppLayout() {
    const location = useLocation()
    const navigate = useNavigate()
    const scenario = useScenarioParam()
    const selectedRole = useSessionStore((state) => state.selectedRole)
    const theme = useThemeStore((state) => state.theme)
    const toggleTheme = useThemeStore((state) => state.toggleTheme)
    const sessionQuery = useSessionQuery({ scenario })
    const logoutMutation = useLogoutSessionMutation()
    const session = sessionQuery.data
    const roleLabel = getExperienceRoleLabel(session?.user.role ?? selectedRole)
    const availableNav = workspaceNav.filter((item) => canAccessPath(session?.user.role ?? selectedRole, item.path))
    const fullBleedSurface = isChatRoute(location.pathname)

    return (
        <div className="min-h-screen text-gray-900 transition-colors dark:text-white">
            <header className="sticky top-0 z-30 border-b border-white/60 bg-white/72 backdrop-blur-xl dark:border-white/10 dark:bg-[#08111f]/78">
                <div className="mx-auto flex max-w-[1760px] flex-wrap items-center gap-3 px-4 py-4 md:px-8">
                    <RouteIntentLink to="/chat" className="min-w-fit">
                        <div className="flex items-center gap-3">
                            <div className="flex flex-col">
                                <div className="flex items-end gap-3">
                                    <span className="text-[2rem] font-black tracking-[0.18em] text-brand-600">UIT</span>
                                    <span className="pb-1 text-[0.65rem] font-semibold uppercase tracking-[0.32em] text-brand-500">Portal</span>
                                </div>
                                <span className="text-2xl font-bold tracking-tight text-gray-950 dark:text-white">UIT AI</span>
                            </div>
                        </div>
                    </RouteIntentLink>

                    <nav className="order-3 flex w-full gap-2 overflow-x-auto pb-1 no-scrollbar md:order-2 md:w-auto md:flex-1 md:justify-center md:pb-0">
                        {availableNav.map((item) => {
                            const isActive =
                                location.pathname === item.path ||
                                (item.path === '/chat' && (location.pathname === '/' || location.pathname.startsWith('/documents/')))

                            return (
                                <RouteIntentLink
                                    key={item.path}
                                    to={item.path}
                                    className={cn(
                                        'relative inline-flex items-center rounded-full border px-4 py-2.5 text-sm font-semibold transition-all duration-200',
                                        isActive
                                            ? 'border-brand-200 bg-brand-50 text-brand-700 shadow-theme-xs dark:border-brand-800 dark:bg-brand-950/70 dark:text-brand-200'
                                            : 'border-gray-200 bg-white/92 text-gray-600 hover:-translate-y-0.5 hover:border-brand-200 hover:text-brand-700 hover:shadow-theme-xs dark:border-gray-700 dark:bg-gray-900/92 dark:text-gray-200 dark:hover:border-brand-800 dark:hover:text-brand-200',
                                    )}
                                >
                                    <span>{item.label}</span>
                                </RouteIntentLink>
                            )
                        })}
                    </nav>

                    <div className="order-2 ml-auto flex items-center gap-2 md:order-3">
                        <Badge tone="brand" className="hidden md:inline-flex">
                            {roleLabel}
                        </Badge>

                        <Button variant="secondary" size="sm" onClick={toggleTheme} aria-label="Đổi giao diện sáng tối">
                            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
                            <span className="hidden sm:inline">{theme === 'dark' ? 'Sáng' : 'Tối'}</span>
                        </Button>

                        <Button
                            variant="secondary"
                            size="sm"
                            isLoading={logoutMutation.isPending}
                            onClick={async () => {
                                await logoutMutation.mutateAsync()
                                navigate('/auth/login', { replace: true })
                            }}
                        >
                            <LogOut size={16} />
                            <span className="hidden sm:inline">Đăng xuất</span>
                        </Button>
                    </div>
                </div>
            </header>

            <main className={cn('flex-1', fullBleedSurface ? 'px-0 py-0' : 'px-4 py-6 md:px-8 md:py-8')}>
                <AnimatePresence mode="wait">
                    <motion.div
                        key={location.pathname}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.2, ease: 'easeOut' }}
                        className={cn(fullBleedSurface ? 'min-h-[calc(100vh-5.5rem)]' : 'mx-auto max-w-7xl')}
                    >
                        <Outlet />
                    </motion.div>
                </AnimatePresence>
            </main>
        </div>
    )
}
