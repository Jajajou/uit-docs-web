import {
    Bot,
    ClipboardList,
    FileSearch,
    Files,
    Home,
    LayoutDashboard,
    Library,
    LogIn,
    ScrollText,
    Settings,
    ShieldCheck,
    Upload,
    Users,
    Workflow,
} from 'lucide-react'
import { matchPath } from 'react-router-dom'
import type { Role, Session } from '@/entities/auth/types'
import type { SidebarNavItem } from '@/shared/ui/composites/Sidebar'

export type AppShellKind = 'public' | 'auth' | 'portal' | 'admin' | 'system'

export interface AppRouteMeta {
    path: string
    title: string
    shell: AppShellKind
    allowedRoles: Role[]
    navLabel?: string
    icon?: SidebarNavItem['icon']
}

export const allRoles: Role[] = ['guest', 'student', 'lecturer', 'operator', 'admin']
export const internalRoles: Role[] = ['lecturer', 'operator', 'admin']
export const portalContributorRoles: Role[] = ['lecturer', 'operator', 'admin']
export const portalOperatorRoles: Role[] = ['operator', 'admin']
export const INTERNAL_EMAIL_DOMAIN = '@gm.uit.edu.vn'

export const routeMeta: AppRouteMeta[] = [
    { path: '/', title: 'Trang chu', shell: 'public', allowedRoles: allRoles, navLabel: 'Home', icon: Home },
    { path: '/chat', title: 'Chat', shell: 'public', allowedRoles: allRoles, navLabel: 'Chat', icon: Bot },
    { path: '/documents/:id', title: 'Document detail', shell: 'public', allowedRoles: allRoles, navLabel: 'Documents', icon: FileSearch },
    { path: '/auth/login', title: 'Login', shell: 'auth', allowedRoles: allRoles, navLabel: 'Login', icon: LogIn },
    { path: '/auth/callback', title: 'Auth callback', shell: 'auth', allowedRoles: allRoles },
    { path: '/403', title: 'Access denied', shell: 'system', allowedRoles: allRoles },
    { path: '/portal', title: 'Portal overview', shell: 'portal', allowedRoles: portalContributorRoles, navLabel: 'Overview', icon: LayoutDashboard },
    { path: '/portal/upload', title: 'Upload', shell: 'portal', allowedRoles: portalContributorRoles, navLabel: 'Upload', icon: Upload },
    { path: '/portal/submissions', title: 'Submissions', shell: 'portal', allowedRoles: portalContributorRoles, navLabel: 'Submissions', icon: Files },
    { path: '/portal/submissions/:id', title: 'Submission detail', shell: 'portal', allowedRoles: portalContributorRoles },
    { path: '/portal/review', title: 'Review queue', shell: 'portal', allowedRoles: portalOperatorRoles, navLabel: 'Review', icon: ClipboardList },
    { path: '/portal/library', title: 'Library', shell: 'portal', allowedRoles: portalOperatorRoles, navLabel: 'Library', icon: Library },
    { path: '/portal/jobs', title: 'Jobs', shell: 'portal', allowedRoles: portalOperatorRoles, navLabel: 'Jobs', icon: Workflow },
    { path: '/admin/users', title: 'Users', shell: 'admin', allowedRoles: ['admin'], navLabel: 'Users', icon: Users },
    { path: '/admin/roles', title: 'Roles', shell: 'admin', allowedRoles: ['admin'], navLabel: 'Roles', icon: ShieldCheck },
    { path: '/admin/settings', title: 'Settings', shell: 'admin', allowedRoles: ['admin'], navLabel: 'Settings', icon: Settings },
    { path: '/admin/audit-logs', title: 'Audit logs', shell: 'admin', allowedRoles: ['admin'], navLabel: 'Audit logs', icon: ScrollText },
]

export const publicNavItems: SidebarNavItem[] = routeMeta
    .filter((route) => route.shell === 'public' && route.navLabel && route.icon)
    .map((route) => ({
        label: route.navLabel!,
        path: route.path.replace('/:id', '/doc-001'),
        icon: route.icon!,
    }))

export const portalNavItems: SidebarNavItem[] = routeMeta
    .filter((route) => route.shell === 'portal' && route.navLabel && route.icon)
    .map((route) => ({
        label: route.navLabel!,
        path: route.path,
        icon: route.icon!,
    }))

export const adminNavItems: SidebarNavItem[] = routeMeta
    .filter((route) => route.shell === 'admin' && route.navLabel && route.icon)
    .map((route) => ({
        label: route.navLabel!,
        path: route.path,
        icon: route.icon!,
    }))

export function getRouteMeta(pathname: string) {
    return routeMeta.find((route) => matchPath({ path: route.path, end: true }, pathname))
}

export function canAccessPath(role: Role, pathname: string) {
    const meta = getRouteMeta(pathname)

    if (!meta) {
        return true
    }

    return meta.allowedRoles.includes(role)
}

export function isInternalRole(role: Role) {
    return internalRoles.includes(role)
}

export function hasRequiredInternalEmail(role: Role, email: string) {
    return !isInternalRole(role) || email.toLowerCase().endsWith(INTERNAL_EMAIL_DOMAIN)
}

export function canAccessSessionPath(session: Session, pathname: string) {
    return canAccessPath(session.user.role, pathname) && hasRequiredInternalEmail(session.user.role, session.user.email)
}

export function getDefaultPathForRole(role: Role) {
    if (role === 'admin') {
        return '/admin/users'
    }

    if (role === 'guest' || role === 'student') {
        return '/'
    }

    return '/portal'
}
