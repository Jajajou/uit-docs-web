import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'
import { buildAuthCallbackTarget } from '@/entities/auth/bootstrap'
import { useLogoutSessionMutation } from '@/entities/auth/queries'
import { useSessionStore } from '@/entities/auth/store'
import type { Role } from '@/entities/auth/types'
import { isMockAdapterEnabled } from '@/shared/api/mockRuntime'
import { Button } from '@/shared/ui/primitives/Button'
import { Select } from '@/shared/ui/primitives/Select'

const roleOptions: Array<{ value: Role; label: string }> = [
    { value: 'student', label: 'Student' },
    { value: 'teacher', label: 'Teacher' },
    { value: 'admin', label: 'Admin' },
]

export function RoleSwitcher() {
    const location = useLocation()
    const navigate = useNavigate()
    const selectedRole = useSessionStore((state) => state.selectedRole)
    const beginBootstrap = useSessionStore((state) => state.beginBootstrap)
    const queryClient = useQueryClient()
    const logoutMutation = useLogoutSessionMutation()

    if (!isMockAdapterEnabled) {
        return (
            <Button
                type="button"
                variant="secondary"
                onClick={() => {
                    navigate('/auth/login', { replace: true })
                    logoutMutation.mutate()
                }}
            >
                Sign out
            </Button>
        )
    }

    return (
        <Select
            aria-label="Switch role"
            value={selectedRole}
            onChange={(event) => {
                const nextRole = event.target.value as Role
                const returnTo = `${location.pathname}${location.search}`

                beginBootstrap(nextRole, returnTo)
                queryClient.removeQueries({ queryKey: ['auth', 'session'] })
                navigate(buildAuthCallbackTarget(nextRole, returnTo))
            }}
            options={roleOptions}
            className="min-w-40"
        />
    )
}
