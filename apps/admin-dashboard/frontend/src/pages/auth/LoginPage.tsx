import { useLocation, useNavigate } from 'react-router-dom'
import { LogIn, ShieldCheck } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { INTERNAL_EMAIL_DOMAIN } from '@/app/config/routes'
import { buildAuthCallbackTarget, buildInternalSsoStartTarget } from '@/entities/auth/bootstrap'
import { useSsoProviderMetadataQuery } from '@/entities/auth/queries'
import { useSessionStore } from '@/entities/auth/store'
import type { Role } from '@/entities/auth/types'
import { isMockAdapterEnabled } from '@/shared/api/mockRuntime'
import { Badge, Button, Card, PageHeader } from '@/shared/ui'

const publicLoginOptions: Array<{ role: Role; label: string; description: string }> = [
    { role: 'guest', label: 'Continue as guest', description: 'Public shell only.' },
    { role: 'student', label: 'Student account', description: 'Student-facing public shell.' },
]

const internalDemoOptions: Array<{ role: Role; label: string; description: string }> = [
    { role: 'lecturer', label: `Lecturer ${INTERNAL_EMAIL_DOMAIN}`, description: 'Portal upload and submissions.' },
    { role: 'operator', label: `Operator ${INTERNAL_EMAIL_DOMAIN}`, description: 'Portal review, library and jobs.' },
    { role: 'admin', label: `Admin ${INTERNAL_EMAIL_DOMAIN}`, description: 'Portal plus admin shell.' },
]

export default function LoginPage() {
    const location = useLocation()
    const navigate = useNavigate()
    const queryClient = useQueryClient()
    const beginBootstrap = useSessionStore((state) => state.beginBootstrap)
    const requestedReturnTo = new URLSearchParams(location.search).get('returnTo')
    const ssoMetadataQuery = useSsoProviderMetadataQuery({ enabled: !isMockAdapterEnabled })
    const providerMetadata = ssoMetadataQuery.data

    return (
        <div className="space-y-6">
            <PageHeader
                title={isMockAdapterEnabled ? 'Session bootstrap' : 'Sign in'}
                description={
                    isMockAdapterEnabled
                        ? 'Choose the role to hydrate `/api/auth/me`, then continue through the callback route used by the auth shell.'
                        : 'Public and student access still use local bootstrap inside `/web`. Internal staff accounts now start through backend-owned institutional SSO.'
                }
                icon={LogIn}
            />
            <div className="grid gap-4">
                {publicLoginOptions.map((option) => (
                    <Card key={option.role} className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                        <div className="space-y-1">
                            <div className="text-base font-semibold text-gray-900 dark:text-white">{option.label}</div>
                            <div className="text-sm text-gray-500">{option.description}</div>
                        </div>
                        <Button
                            onClick={() => {
                                beginBootstrap(option.role, requestedReturnTo)
                                queryClient.removeQueries({ queryKey: ['auth', 'session'] })
                                navigate(buildAuthCallbackTarget(option.role, requestedReturnTo))
                            }}
                        >
                            <ShieldCheck size={16} />
                            Continue as {option.role}
                        </Button>
                    </Card>
                ))}
                {isMockAdapterEnabled ? (
                    internalDemoOptions.map((option) => (
                        <Card key={option.role} className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                            <div className="space-y-1">
                                <div className="text-base font-semibold text-gray-900 dark:text-white">{option.label}</div>
                                <div className="text-sm text-gray-500">{option.description}</div>
                            </div>
                            <Button
                                onClick={() => {
                                    beginBootstrap(option.role, requestedReturnTo)
                                    queryClient.removeQueries({ queryKey: ['auth', 'session'] })
                                    navigate(buildAuthCallbackTarget(option.role, requestedReturnTo))
                                }}
                            >
                                <ShieldCheck size={16} />
                                Continue as {option.role}
                            </Button>
                        </Card>
                    ))
                ) : (
                    <Card className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                        <div className="space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                                <div className="text-base font-semibold text-gray-900 dark:text-white">
                                    {providerMetadata?.providerName ?? 'Internal SSO'} {INTERNAL_EMAIL_DOMAIN}
                                </div>
                                {providerMetadata ? (
                                    <Badge tone={providerMetadata.usesLocalEmulator ? 'warning' : 'brand'}>
                                        {providerMetadata.usesLocalEmulator ? 'Local emulator' : 'Provider-ready'}
                                    </Badge>
                                ) : null}
                            </div>
                            <div className="text-sm text-gray-500">
                                Lecturer, operator, and admin access now begin on the backend.
                                {providerMetadata?.usesLocalEmulator
                                    ? ' The current /web environment is still using the local provider emulator before returning to /auth/callback.'
                                    : providerMetadata?.configured
                                      ? ' The backend is configured for a provider-owned redirect while preserving the same /auth/callback contract.'
                                      : ' The backend auth contract is ready, but provider metadata is not configured yet.'}
                            </div>
                            {providerMetadata ? (
                                <div className="flex flex-wrap gap-2 pt-1 text-xs text-gray-500">
                                    <Badge tone="neutral">Callback {providerMetadata.callbackPath}</Badge>
                                    <Badge tone="neutral">Role claim {providerMetadata.roleClaim}</Badge>
                                    <Badge tone="neutral">Group claim {providerMetadata.groupClaim}</Badge>
                                </div>
                            ) : null}
                        </div>
                        <Button
                            disabled={providerMetadata ? !providerMetadata.configured : false}
                            onClick={() => {
                                window.location.assign(buildInternalSsoStartTarget(requestedReturnTo))
                            }}
                        >
                            <ShieldCheck size={16} />
                            Continue with internal SSO
                        </Button>
                    </Card>
                )}
            </div>
        </div>
    )
}
