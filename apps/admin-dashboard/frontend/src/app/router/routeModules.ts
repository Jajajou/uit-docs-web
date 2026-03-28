export const loadPublicLayout = () => import('@/layouts/PublicLayout')
export const loadAuthLayout = () => import('@/layouts/AuthLayout')
export const loadPortalLayout = () => import('@/layouts/PortalLayout')
export const loadAdminLayout = () => import('@/layouts/AdminLayout')

export const loadHomePage = () => import('@/pages/public/HomePage')
export const loadChatPage = () => import('@/pages/public/ChatPage')
export const loadDocumentDetailPage = () => import('@/pages/public/DocumentDetailPage')

export const loadLoginPage = () => import('@/pages/auth/LoginPage')
export const loadAuthCallbackPage = () => import('@/pages/auth/AuthCallbackPage')

export const loadPortalOverviewPage = () => import('@/pages/portal/PortalOverviewPage')
export const loadUploadPage = () => import('@/pages/portal/UploadPage')
export const loadSubmissionsPage = () => import('@/pages/portal/SubmissionsPage')
export const loadSubmissionDetailPage = () => import('@/pages/portal/SubmissionDetailPage')
export const loadReviewPage = () => import('@/pages/portal/ReviewPage')
export const loadLibraryPage = () => import('@/pages/portal/LibraryPage')
export const loadJobsPage = () => import('@/pages/portal/JobsPage')

export const loadUsersPage = () => import('@/pages/admin/UsersPage')
export const loadRolesPage = () => import('@/pages/admin/RolesPage')
export const loadSettingsPage = () => import('@/pages/admin/SettingsPage')
export const loadAuditLogsPage = () => import('@/pages/admin/AuditLogsPage')

export const loadForbiddenPage = () => import('@/pages/system/ForbiddenPage')
export const loadNotFoundPage = () => import('@/pages/system/NotFoundPage')

type IdleCallbackHandle = number
type IdleTask = () => void
type NetworkConnection = {
    saveData?: boolean
    effectiveType?: string
}

interface RoutePreloader {
    key: string
    matches: (pathname: string) => boolean
    load: () => Promise<unknown>
}

const preloadCache = new Map<string, Promise<unknown>>()

const routePreloaders: RoutePreloader[] = [
    {
        key: 'public-home',
        matches: (pathname) => pathname === '/',
        load: () => Promise.all([loadPublicLayout(), loadHomePage()]),
    },
    {
        key: 'public-chat',
        matches: (pathname) => pathname === '/chat',
        load: () => Promise.all([loadPublicLayout(), loadChatPage()]),
    },
    {
        key: 'public-document-detail',
        matches: (pathname) => pathname.startsWith('/documents/'),
        load: () => Promise.all([loadPublicLayout(), loadDocumentDetailPage()]),
    },
    {
        key: 'auth-login',
        matches: (pathname) => pathname === '/auth/login',
        load: () => Promise.all([loadAuthLayout(), loadLoginPage()]),
    },
    {
        key: 'auth-callback',
        matches: (pathname) => pathname === '/auth/callback',
        load: () => Promise.all([loadAuthLayout(), loadAuthCallbackPage()]),
    },
    {
        key: 'portal-overview',
        matches: (pathname) => pathname === '/portal',
        load: () => Promise.all([loadPortalLayout(), loadPortalOverviewPage()]),
    },
    {
        key: 'portal-upload',
        matches: (pathname) => pathname === '/portal/upload',
        load: () => Promise.all([loadPortalLayout(), loadUploadPage()]),
    },
    {
        key: 'portal-submissions',
        matches: (pathname) => pathname === '/portal/submissions',
        load: () => Promise.all([loadPortalLayout(), loadSubmissionsPage()]),
    },
    {
        key: 'portal-submission-detail',
        matches: (pathname) => pathname.startsWith('/portal/submissions/'),
        load: () => Promise.all([loadPortalLayout(), loadSubmissionDetailPage()]),
    },
    {
        key: 'portal-review',
        matches: (pathname) => pathname === '/portal/review',
        load: () => Promise.all([loadPortalLayout(), loadReviewPage()]),
    },
    {
        key: 'portal-library',
        matches: (pathname) => pathname === '/portal/library',
        load: () => Promise.all([loadPortalLayout(), loadLibraryPage()]),
    },
    {
        key: 'portal-jobs',
        matches: (pathname) => pathname === '/portal/jobs',
        load: () => Promise.all([loadPortalLayout(), loadJobsPage()]),
    },
    {
        key: 'admin-users',
        matches: (pathname) => pathname === '/admin/users',
        load: () => Promise.all([loadAdminLayout(), loadUsersPage()]),
    },
    {
        key: 'admin-roles',
        matches: (pathname) => pathname === '/admin/roles',
        load: () => Promise.all([loadAdminLayout(), loadRolesPage()]),
    },
    {
        key: 'admin-settings',
        matches: (pathname) => pathname === '/admin/settings',
        load: () => Promise.all([loadAdminLayout(), loadSettingsPage()]),
    },
    {
        key: 'admin-audit-logs',
        matches: (pathname) => pathname === '/admin/audit-logs',
        load: () => Promise.all([loadAdminLayout(), loadAuditLogsPage()]),
    },
    {
        key: 'system-forbidden',
        matches: (pathname) => pathname === '/403',
        load: loadForbiddenPage,
    },
    {
        key: 'system-not-found',
        matches: () => true,
        load: loadNotFoundPage,
    },
]

function getIdleSupport() {
    if (typeof window === 'undefined') {
        return undefined
    }

    return window as Window &
        typeof globalThis & {
            requestIdleCallback?: (callback: IdleRequestCallback, options?: IdleRequestOptions) => IdleCallbackHandle
            cancelIdleCallback?: (handle: IdleCallbackHandle) => void
        }
}

export function canPrefetchRouteAssets() {
    if (typeof navigator === 'undefined') {
        return true
    }

    const connection = (navigator as Navigator & { connection?: NetworkConnection }).connection

    if (!connection) {
        return true
    }

    if (connection.saveData) {
        return false
    }

    return connection.effectiveType !== 'slow-2g' && connection.effectiveType !== '2g'
}

function loadOnce(key: string, loader: () => Promise<unknown>) {
    const existing = preloadCache.get(key)

    if (existing) {
        return existing
    }

    const request = loader().catch((error) => {
        preloadCache.delete(key)
        throw error
    })

    preloadCache.set(key, request)
    return request
}

export function normalizeRoutePath(pathname: string) {
    return pathname.split(/[?#]/, 1)[0] ?? pathname
}

export function prefetchRoute(pathname: string) {
    if (!canPrefetchRouteAssets()) {
        return Promise.resolve()
    }

    const normalizedPath = normalizeRoutePath(pathname)
    const preloader = routePreloaders.find((candidate) => candidate.matches(normalizedPath))

    if (!preloader) {
        return Promise.resolve()
    }

    return loadOnce(preloader.key, preloader.load)
}

export function scheduleIdleTask(task: IdleTask, timeout = 1_200) {
    const idleSupport = getIdleSupport()

    if (!idleSupport || !canPrefetchRouteAssets() || document.visibilityState === 'hidden') {
        return () => undefined
    }

    if (idleSupport?.requestIdleCallback) {
        const handle = idleSupport.requestIdleCallback(() => task(), { timeout })
        return () => idleSupport.cancelIdleCallback?.(handle)
    }

    const timer = idleSupport.setTimeout(task, 300)
    return () => idleSupport.clearTimeout(timer)
}

export function scheduleRoutePrefetch(pathname: string, timeout?: number) {
    return scheduleIdleTask(() => {
        void prefetchRoute(pathname)
    }, timeout)
}
