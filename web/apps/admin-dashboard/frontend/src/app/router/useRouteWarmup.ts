import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { normalizeRoutePath, scheduleRoutePrefetch } from '@/app/router/routeModules'

export function useRouteWarmup(pathname: string, enabled = true) {
    const location = useLocation()

    useEffect(() => {
        if (!enabled || normalizeRoutePath(location.pathname) === normalizeRoutePath(pathname)) {
            return undefined
        }

        return scheduleRoutePrefetch(pathname)
    }, [enabled, location.pathname, pathname])
}
