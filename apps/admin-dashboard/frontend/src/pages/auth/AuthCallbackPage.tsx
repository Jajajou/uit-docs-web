import { useEffect, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { LogIn, ShieldCheck } from 'lucide-react'
import { INTERNAL_EMAIL_DOMAIN } from '@/app/config/routes'
import {
    buildAuthCallbackTarget,
    buildInternalSsoStartTarget,
    readAuthError,
    readAuthErrorMessage,
    readBootstrapReturnTo,
    readBootstrapRole,
    resolveSessionRedirectPath,
} from '@/entities/auth/bootstrap'
import { useBootstrapSessionMutation, useSessionQuery } from '@/entities/auth/queries'
import { useSessionStore } from '@/entities/auth/store'
import { useScenarioParam } from '@/shared/lib/scenario'
import { Badge, Button, Card, PageHeader } from '@/shared/ui'

export default function AuthCallbackPage() {
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()
    const scenario = useScenarioParam()
    const selectedRole = useSessionStore((state) => state.selectedRole)
    const bootstrapRequest = useSessionStore((state) => state.bootstrapRequest)
    const clearBootstrap = useSessionStore((state) => state.clearBootstrap)
    const setRole = useSessionStore((state) => state.setRole)

    const hasExplicitBootstrap = searchParams.get('bootstrap') === '1' || bootstrapRequest !== null
    const requestedRole = readBootstrapRole(searchParams) ?? bootstrapRequest?.role ?? null
    const requestedReturnTo = readBootstrapReturnTo(searchParams) ?? bootstrapRequest?.returnTo ?? null
    const authErrorCode = readAuthError(searchParams)
    const authErrorMessage = readAuthErrorMessage(searchParams)
    const {
        data: bootstrapSession,
        error: bootstrapError,
        isError: isBootstrapError,
        isPending: isBootstrapping,
        mutate: bootstrapRole,
        reset: resetBootstrapMutation,
        status: bootstrapStatus,
    } = useBootstrapSessionMutation({ scenario })
    const sessionQuery = useSessionQuery({ scenario, enabled: !hasExplicitBootstrap && !authErrorCode })
    const activeSession = bootstrapSession ?? sessionQuery.data
    const activeError = bootstrapError ?? sessionQuery.error

    const redirectTarget = useMemo(
        () => (activeSession ? resolveSessionRedirectPath(activeSession.user.role, requestedReturnTo) : null),
        [activeSession, requestedReturnTo],
    )

    useEffect(() => {
        if (hasExplicitBootstrap && requestedRole && bootstrapStatus === 'idle') {
            bootstrapRole(requestedRole)
        }
    }, [bootstrapRole, bootstrapStatus, hasExplicitBootstrap, requestedRole])

    useEffect(() => {
        if (activeSession && redirectTarget) {
            setRole(activeSession.user.role)
            clearBootstrap()
            navigate(redirectTarget, { replace: true })
        }
    }, [activeSession, clearBootstrap, navigate, redirectTarget, setRole])

    if (authErrorCode || isBootstrapError || sessionQuery.isError || (hasExplicitBootstrap && !requestedRole)) {
        const errorMessage =
            authErrorMessage
                ? authErrorMessage
                : hasExplicitBootstrap && !requestedRole
                ? 'The callback is missing a valid requested role, so the auth shell cannot bootstrap a session.'
                : activeError instanceof Error
                  ? activeError.message
                  : 'The auth shell could not establish the requested session.'
        const retrySso = !hasExplicitBootstrap && authErrorCode

        return (
            <div className="space-y-6">
                <PageHeader
                    title="Session callback"
                    description="The auth shell could not establish the requested session from `/api/auth/bootstrap`, complete the backend-owned SSO handoff, or validate `/api/auth/me`."
                    icon={LogIn}
                />
                <Card className="space-y-4">
                    <div className="space-y-2">
                        <div className="flex flex-wrap gap-2">
                            {authErrorCode ? <Badge tone="warning">Auth error {authErrorCode}</Badge> : null}
                            {requestedRole ? <Badge tone="warning">Requested role {requestedRole}</Badge> : null}
                            {!authErrorCode && !requestedRole ? <Badge tone="warning">Missing requested role</Badge> : null}
                            {requestedReturnTo ? <Badge tone="neutral">Return target {requestedReturnTo}</Badge> : null}
                        </div>
                        <p className="text-sm text-error-700 dark:text-error-300">{errorMessage}</p>
                    </div>
                    <div className="flex flex-wrap gap-3">
                        {retrySso ? (
                            <Button
                                type="button"
                                onClick={() => {
                                    window.location.assign(buildInternalSsoStartTarget(requestedReturnTo))
                                }}
                            >
                                Retry internal SSO
                            </Button>
                        ) : (
                            <Button
                                type="button"
                                onClick={() => {
                                    if (requestedRole && hasExplicitBootstrap) {
                                        navigate(buildAuthCallbackTarget(requestedRole, requestedReturnTo), { replace: true })
                                        resetBootstrapMutation()
                                        bootstrapRole(requestedRole)
                                        return
                                    }

                                    void sessionQuery.refetch()
                                }}
                            >
                                {hasExplicitBootstrap ? 'Retry bootstrap' : 'Retry session check'}
                            </Button>
                        )}
                        <Button type="button" variant="secondary" onClick={() => navigate('/auth/login', { replace: true })}>
                            Back to login
                        </Button>
                    </div>
                </Card>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <PageHeader
                title="Session callback"
                description="The auth shell is completing the requested session through `/api/auth/bootstrap` or backend-owned SSO, validating `/api/auth/me`, then redirecting to the safest allowed shell target."
                icon={LogIn}
            />
            <Card className="space-y-4">
                <div className="flex flex-wrap gap-2">
                    {requestedRole ? <Badge tone="brand">Requested role {requestedRole}</Badge> : <Badge tone="brand">Current role {selectedRole}</Badge>}
                    <Badge tone="neutral">Store role {selectedRole}</Badge>
                    {redirectTarget ? <Badge tone="success">Next {redirectTarget}</Badge> : null}
                </div>
                {requestedRole && ['lecturer', 'operator', 'admin'].includes(requestedRole) ? (
                    <div className="rounded-2xl border border-brand-200 bg-brand-50 p-4 text-sm text-brand-800 dark:border-brand-900 dark:bg-brand-950 dark:text-brand-200">
                        <div className="flex items-center gap-2 font-semibold">
                            <ShieldCheck size={16} />
                            Internal account bootstrap
                        </div>
                        <p className="mt-2">
                            Internal roles require an institutional email ending in `{INTERNAL_EMAIL_DOMAIN}` before the route guard will allow portal or admin access.
                        </p>
                    </div>
                ) : null}
                <p className="text-sm text-gray-600 dark:text-gray-300">
                    {hasExplicitBootstrap && requestedRole
                        ? isBootstrapping
                            ? `Bootstrapping ${requestedRole} via /api/auth/bootstrap before redirect...`
                            : activeSession
                              ? `Resolved ${activeSession.user.role} session for ${activeSession.user.email}. Redirecting now...`
                              : 'Waiting for auth bootstrap to complete...'
                        : activeSession
                          ? `Validated ${activeSession.user.role} session for ${activeSession.user.email}. Redirecting now...`
                          : 'Loading the current session from `/api/auth/me` after backend SSO handoff...'}
                </p>
            </Card>
        </div>
    )
}
