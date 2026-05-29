import { canAccessPath, getDefaultPathForRole } from '@/app/config/routes'
import { isRole } from '@/entities/auth/roles'
import type { Role } from '@/entities/auth/types'

export interface SessionBootstrapRequest {
    role: Role
    returnTo: string | null
    initiatedAt: string
}

export function buildAuthCallbackTarget(role: Role, returnTo?: string | null) {
    const params = new URLSearchParams({
        bootstrap: '1',
        role,
    })

    if (returnTo) {
        params.set('returnTo', returnTo)
    }

    return `/auth/callback?${params.toString()}`
}

export function buildInternalSsoStartTarget(returnTo?: string | null) {
    const params = new URLSearchParams()

    if (returnTo && returnTo.startsWith('/')) {
        params.set('returnTo', returnTo)
    }

    const query = params.toString()
    return query ? `/api/auth/sso/start?${query}` : '/api/auth/sso/start'
}

export function readBootstrapRole(searchParams: URLSearchParams): Role | null {
    const value = searchParams.get('role')

    if (isRole(value)) {
        return value
    }

    return null
}

export function readBootstrapReturnTo(searchParams: URLSearchParams) {
    const value = searchParams.get('returnTo')
    return value && value.startsWith('/') ? value : null
}

export function readAuthError(searchParams: URLSearchParams) {
    const value = searchParams.get('authError')
    return value && value.trim().length > 0 ? value : null
}

export function readAuthErrorMessage(searchParams: URLSearchParams) {
    const value = searchParams.get('authErrorMessage')
    return value && value.trim().length > 0 ? value : null
}

function toAccessPath(pathname: string) {
    return pathname.split('?')[0].split('#')[0]
}

export function resolveSessionRedirectPath(role: Role, returnTo?: string | null) {
    if (returnTo && canAccessPath(role, toAccessPath(returnTo))) {
        return returnTo
    }

    return getDefaultPathForRole(role)
}
