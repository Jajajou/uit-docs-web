import {
    Bot,
    Upload,
    ShieldCheck,
    LogIn,
    FileSearch
} from 'lucide-react'
import { matchPath } from 'react-router-dom'
import { appRoles, isInternalRole } from '@/entities/auth/roles'
import type { Role, Session } from '@/entities/auth/types'
import type { SidebarNavItem } from '@/shared/ui/composites/Sidebar'

export type AppShellKind = 'app' | 'auth' | 'system'

export interface AppRouteMeta {
    path: string
    title: string
    shell: AppShellKind
    allowedRoles: Role[]
    navLabel?: string
    icon?: SidebarNavItem['icon']
}

export const allRoles: Role[] = [...appRoles]
export const internalRoles: Role[] = ['teacher', 'admin']
export const portalContributorRoles: Role[] = ['teacher', 'admin']
export const adminControlRoles: Role[] = ['admin']
export const INTERNAL_EMAIL_DOMAIN = '@gm.uit.edu.vn'

export const routeMeta: AppRouteMeta[] = [
    { path: '/', title: 'Chat', shell: 'app', allowedRoles: allRoles, navLabel: 'Chat', icon: Bot },
    { path: '/chat', title: 'Chat', shell: 'app', allowedRoles: allRoles, navLabel: 'Chat', icon: Bot },
    { path: '/knowledge', title: 'Tải lên', shell: 'app', allowedRoles: portalContributorRoles },
    { path: '/documents/:id', title: 'Chi tiết tài liệu', shell: 'app', allowedRoles: allRoles, navLabel: 'Tài liệu', icon: FileSearch },
    { path: '/upload', title: 'Tải lên', shell: 'app', allowedRoles: portalContributorRoles, navLabel: 'Tải lên', icon: Upload },
    { path: '/manager', title: 'Quản trị', shell: 'app', allowedRoles: adminControlRoles, navLabel: 'Quản trị', icon: ShieldCheck },
    { path: '/auth/login', title: 'Đăng nhập', shell: 'auth', allowedRoles: allRoles, navLabel: 'Đăng nhập', icon: LogIn },
    { path: '/auth/callback', title: 'Xác thực', shell: 'auth', allowedRoles: allRoles },
    { path: '/403', title: 'Không có quyền truy cập', shell: 'system', allowedRoles: allRoles },
]

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

export function getExperienceRole(role: Role) {
    return role
}

export function getExperienceRoleLabel(role: Role) {
    const experienceRole = getExperienceRole(role)

    if (experienceRole === 'teacher') {
        return 'Giảng viên'
    }

    if (experienceRole === 'admin') {
        return 'Quản trị viên'
    }

    return 'Sinh viên'
}

export function hasRequiredInternalEmail(role: Role, email: string) {
    return !isInternalRole(role) || email.toLowerCase().endsWith(INTERNAL_EMAIL_DOMAIN)
}

export function canAccessSessionPath(session: Session, pathname: string) {
    return canAccessPath(session.user.role, pathname) && hasRequiredInternalEmail(session.user.role, session.user.email)
}

export function getDefaultPathForRole(_role: Role) {
    return '/chat'
}
