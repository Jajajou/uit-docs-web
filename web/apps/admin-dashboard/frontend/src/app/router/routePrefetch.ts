import type { To } from 'react-router-dom'
import { prefetchRoute } from '@/app/router/routeModules'

function getRouteTarget(to: To) {
    if (typeof to === 'string') {
        return to
    }

    return to.pathname
}

export function triggerRouteIntentPrefetch(to: To) {
    const pathname = getRouteTarget(to)

    if (!pathname) {
        return
    }

    void prefetchRoute(pathname)
}
