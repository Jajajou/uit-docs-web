import type { ComponentProps } from 'react'
import { Link } from 'react-router-dom'
import { triggerRouteIntentPrefetch } from '@/app/router/routePrefetch'

type LinkMouseEvent = Parameters<NonNullable<ComponentProps<typeof Link>['onMouseEnter']>>[0]
type LinkFocusEvent = Parameters<NonNullable<ComponentProps<typeof Link>['onFocus']>>[0]
type LinkTouchEvent = Parameters<NonNullable<ComponentProps<typeof Link>['onTouchStart']>>[0]

export function RouteIntentLink({
    to,
    onMouseEnter,
    onFocus,
    onTouchStart,
    ...props
}: ComponentProps<typeof Link>) {
    const handleIntent = () => triggerRouteIntentPrefetch(to)

    return (
        <Link
            to={to}
            onMouseEnter={(event: LinkMouseEvent) => {
                handleIntent()
                onMouseEnter?.(event)
            }}
            onFocus={(event: LinkFocusEvent) => {
                handleIntent()
                onFocus?.(event)
            }}
            onTouchStart={(event: LinkTouchEvent) => {
                handleIntent()
                onTouchStart?.(event)
            }}
            {...props}
        />
    )
}
