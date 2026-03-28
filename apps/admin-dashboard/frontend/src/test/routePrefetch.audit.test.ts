import { afterEach, describe, expect, it, vi } from 'vitest'
import { canPrefetchRouteAssets, scheduleIdleTask } from '@/app/router/routeModules'

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
})

describe('route prefetch audit', () => {
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
})
