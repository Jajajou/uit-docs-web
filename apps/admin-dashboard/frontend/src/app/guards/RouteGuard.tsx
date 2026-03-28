import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'
import { useSessionQuery } from '@/entities/auth/queries'
import { canAccessSessionPath } from '@/app/config/routes'
import { useScenarioParam } from '@/shared/lib/scenario'
import { ApiClientError } from '@/shared/api/error'
import { Button } from '@/shared/ui/primitives/Button'
import { Card } from '@/shared/ui/primitives/Card'
import { Skeleton } from '@/shared/ui/primitives/Skeleton'
import type { Role } from '@/entities/auth/types'

export function RouteGuard({ allowedRoles }: { allowedRoles: Role[] }) {
    const location = useLocation()
    const scenario = useScenarioParam()
    const sessionQuery = useSessionQuery({ scenario })
    const session = sessionQuery.data
    const authError = sessionQuery.error instanceof ApiClientError ? sessionQuery.error : null

    if (sessionQuery.isLoading) {
        return (
            <Card className="m-6 space-y-3">
                <Skeleton className="h-8 w-48" />
                <Skeleton className="h-32 w-full" />
            </Card>
        )
    }

    if (sessionQuery.isError) {
        return (
            <Card className="m-6 space-y-4">
                <div className="space-y-1">
                    <h2 className="text-lg font-semibold text-gray-950 dark:text-white">Unable to validate session</h2>
                    <p className="text-sm text-gray-600 dark:text-gray-300">
                        {authError?.message ?? 'The session check failed before route access could be confirmed.'}
                    </p>
                    {authError?.requestId ? (
                        <p className="text-xs text-gray-500">Request ID: {authError.requestId}</p>
                    ) : null}
                </div>
                <div className="flex flex-wrap gap-3">
                    <Button type="button" onClick={() => void sessionQuery.refetch()}>
                        Retry session check
                    </Button>
                    <Button asChild variant="secondary">
                        <Link to="/auth/login">Switch role</Link>
                    </Button>
                </div>
            </Card>
        )
    }

    if (!session || !allowedRoles.includes(session.user.role) || !canAccessSessionPath(session, location.pathname)) {
        return <Navigate to="/403" replace state={{ from: location.pathname }} />
    }

    return <Outlet />
}
