export const loadAppLayout = () => import('@/layouts/AppLayout')
export const loadAuthLayout = () => import('@/layouts/AuthLayout')

export const loadChatPage = () => import('@/pages/public/ChatPage')
export const loadDocumentDetailPage = () => import('@/pages/public/DocumentDetailPage')

export const loadLoginPage = () => import('@/pages/auth/LoginPage')
export const loadAuthCallbackPage = () => import('@/pages/auth/AuthCallbackPage')

export const loadUploadPage = () => import('@/pages/portal/UploadPage')
export const loadManagerPage = () => import('@/pages/manager/ManagerPage')

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
        key: 'app-chat',
        matches: (pathname) => pathname === '/' || pathname === '/chat',
        load: () => Promise.all([loadAppLayout(), loadChatPage()]),
    },
    {
        key: 'app-upload',
        matches: (pathname) => pathname === '/upload' || pathname === '/knowledge',
        load: () => Promise.all([loadAppLayout(), loadUploadPage()]),
    },
    {
        key: 'app-manager',
        matches: (pathname) => pathname === '/manager',
        load: () => Promise.all([loadAppLayout(), loadManagerPage()]),
    },
    {
        key: 'auth-login',
        matches: (pathname) => pathname === '/auth/login',
        load: () => Promise.all([loadAuthLayout(), loadLoginPage()]),
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
