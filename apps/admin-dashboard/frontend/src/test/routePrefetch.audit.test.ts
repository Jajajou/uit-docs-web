import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
    canPrefetchRouteAssets,
    normalizeRoutePath,
    prefetchRoute,
    scheduleIdleTask,
    scheduleRoutePrefetch,
} from '@/app/router/routeModules'

const originalConnection = Object.getOwnPropertyDescriptor(navigator, 'connection')
const originalVisibilityState = Object.getOwnPropertyDescriptor(Document.prototype, 'visibilityState')

function setNavigatorConnection(connection: { saveData?: boolean; effectiveType?: string } | undefined) {
    Object.defineProperty(navigator, 'connection', {
        configurable: true,
        value: connection,
    })
}

function setDocumentVisibilityState(state: DocumentVisibilityState) {
    Object.defineProperty(Document.prototype, 'visibilityState', {
        configurable: true,
        get: () => state,
    })
}

function restoreEnvironment() {
    if (originalConnection) {
        Object.defineProperty(navigator, 'connection', originalConnection)
    } else {
        delete (navigator as Navigator & { connection?: unknown }).connection
    }

    if (originalVisibilityState) {
        Object.defineProperty(Document.prototype, 'visibilityState', originalVisibilityState)
    }
}

afterEach(() => {
    restoreEnvironment()
    vi.restoreAllMocks()
    vi.useRealTimers()
})

describe('route prefetch audit', () => {
    beforeEach(() => {
        setDocumentVisibilityState('visible')
        setNavigatorConnection(undefined)
    })

    it('disables prefetch when save-data is enabled', () => {
        setNavigatorConnection({ saveData: true, effectiveType: '4g' })

        expect(canPrefetchRouteAssets()).toBe(false)
    })

    it('disables prefetch on very slow connections', () => {
        setNavigatorConnection({ effectiveType: '2g' })
        expect(canPrefetchRouteAssets()).toBe(false)

        setNavigatorConnection({ effectiveType: 'slow-2g' })
        expect(canPrefetchRouteAssets()).toBe(false)
    })

    it('allows prefetch on normal connections and when connection info is unavailable', () => {
        setNavigatorConnection({ effectiveType: '4g' })
        expect(canPrefetchRouteAssets()).toBe(true)

        setNavigatorConnection(undefined)
        expect(canPrefetchRouteAssets()).toBe(true)
    })

    it('keeps prefetch opt-in when navigator is unavailable', () => {
        const originalNavigator = navigator
        vi.stubGlobal('navigator', undefined)

        expect(canPrefetchRouteAssets()).toBe(true)

        vi.stubGlobal('navigator', originalNavigator)
    })

    it('does not schedule idle work when the tab is hidden', () => {
        const task = vi.fn()
        const setTimeoutSpy = vi.spyOn(window, 'setTimeout')

        setDocumentVisibilityState('hidden')
        const cancel = scheduleIdleTask(task)

        expect(task).not.toHaveBeenCalled()
        expect(setTimeoutSpy).not.toHaveBeenCalled()

        cancel()
    })

    it('does not schedule idle work when save-data is enabled', () => {
        const task = vi.fn()
        const setTimeoutSpy = vi.spyOn(window, 'setTimeout')

        setNavigatorConnection({ saveData: true, effectiveType: '4g' })
        const cancel = scheduleIdleTask(task)

        expect(task).not.toHaveBeenCalled()
        expect(setTimeoutSpy).not.toHaveBeenCalled()

        cancel()
    })

    it('normalizes route paths and caches repeated prefetch requests', () => {
        expect(normalizeRoutePath('/chat?thread=1#reply')).toBe('/chat')

        const first = prefetchRoute('/missing?thread=1')
        const second = prefetchRoute('/missing')

        expect(first).toBe(second)
    })

    it('returns a resolved promise immediately when prefetch is disabled by connection policy', async () => {
        setNavigatorConnection({ saveData: true, effectiveType: '4g' })

        await expect(prefetchRoute('/chat')).resolves.toBeUndefined()
    })

    it('returns a resolved promise when no route preloader can be resolved', async () => {
        const findSpy = vi.spyOn(Array.prototype, 'find')
        findSpy.mockImplementationOnce(() => undefined)

        await expect(prefetchRoute('/chat')).resolves.toBeUndefined()
    })

    it('drops failed preload requests from the cache so the next retry can proceed', async () => {
        const failure = new Error('prefetch failed')
        const findSpy = vi.spyOn(Array.prototype, 'find')

        findSpy.mockImplementationOnce(
            () =>
                ({
                    key: 'forced-failure',
                    matches: () => true,
                    load: () => Promise.reject(failure),
                }) as never,
        )

        await expect(prefetchRoute('/chat')).rejects.toThrow('prefetch failed')
        await expect(prefetchRoute('/chat')).resolves.toBeDefined()
    })

    it('warms the concrete app and auth preloaders without throwing', async () => {
        await expect(prefetchRoute('/chat')).resolves.toBeDefined()
        await expect(prefetchRoute('/documents')).resolves.toBeDefined()
        await expect(prefetchRoute('/library')).resolves.toBeDefined()
        await expect(prefetchRoute('/upload')).resolves.toBeDefined()
        await expect(prefetchRoute('/manager')).resolves.toBeDefined()
        await expect(prefetchRoute('/auth/login')).resolves.toBeDefined()
    })

    it('uses requestIdleCallback when the browser supports it', () => {
        const task = vi.fn()
        const requestIdleCallback = vi.fn((callback: IdleRequestCallback) => {
            callback({ didTimeout: false, timeRemaining: () => 16 } as IdleDeadline)
            return 9
        })
        const cancelIdleCallback = vi.fn()

        Object.defineProperty(window, 'requestIdleCallback', {
            configurable: true,
            value: requestIdleCallback,
        })
        Object.defineProperty(window, 'cancelIdleCallback', {
            configurable: true,
            value: cancelIdleCallback,
        })

        const cancel = scheduleIdleTask(task, 900)

        expect(task).toHaveBeenCalledTimes(1)
        expect(requestIdleCallback).toHaveBeenCalledWith(expect.any(Function), { timeout: 900 })

        cancel()
        expect(cancelIdleCallback).toHaveBeenCalledWith(9)
    })

    it('schedules route prefetch with the timeout fallback when idle callbacks are unavailable', async () => {
        vi.useFakeTimers()

        Object.defineProperty(window, 'requestIdleCallback', {
            configurable: true,
            value: undefined,
        })
        Object.defineProperty(window, 'cancelIdleCallback', {
            configurable: true,
            value: undefined,
        })

        const setTimeoutSpy = vi.spyOn(window, 'setTimeout')
        const clearTimeoutSpy = vi.spyOn(window, 'clearTimeout')

        const cancel = scheduleRoutePrefetch('/manager', 500)

        expect(setTimeoutSpy).toHaveBeenCalled()

        await vi.runAllTimersAsync()
        cancel()

        expect(clearTimeoutSpy).toHaveBeenCalled()
    })

    it('returns a no-op cancel handle when window support is unavailable', () => {
        const originalWindow = window
        vi.stubGlobal('window', undefined)

        const cancel = scheduleIdleTask(vi.fn())

        expect(typeof cancel).toBe('function')

        cancel()
        vi.stubGlobal('window', originalWindow)
    })
})
