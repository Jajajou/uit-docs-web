import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { bootstrapSession, getSession, getSsoProviderMetadata, logoutSession } from '@/entities/auth/api'
import { useSessionStore } from '@/entities/auth/store'
import type { Role, Session } from '@/entities/auth/types'
import { isMockAdapterEnabled } from '@/shared/api/mockRuntime'

export function getSessionQueryKey(role: Role, scenario = 'happy') {
    if (isMockAdapterEnabled) {
        return ['auth', 'session', role, scenario] as const
    }

    return ['auth', 'session', scenario] as const
}

export function useSessionQuery(params?: { scenario?: string; enabled?: boolean }) {
    const selectedRole = useSessionStore((state) => state.selectedRole)
    const setRole = useSessionStore((state) => state.setRole)
    const scenarioKey = params?.scenario ?? 'happy'

    const query = useQuery({
        queryKey: getSessionQueryKey(selectedRole, scenarioKey),
        queryFn: () => getSession(params),
        enabled: params?.enabled ?? true,
    })

    useEffect(() => {
        if (query.data && query.data.user.role !== selectedRole) {
            setRole(query.data.user.role)
        }
    }, [query.data, selectedRole, setRole])

    return query
}

export function useBootstrapSessionMutation(params?: { scenario?: string }) {
    const queryClient = useQueryClient()
    const scenarioKey = params?.scenario ?? 'happy'

    return useMutation({
        mutationFn: (role: Role) => bootstrapSession(role, params),
        onSuccess: (session: Session) => {
            useSessionStore.getState().setRole(session.user.role)
            queryClient.clear()
            queryClient.setQueryData(getSessionQueryKey(session.user.role, scenarioKey), session)
        },
    })
}

export function useLogoutSessionMutation() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: logoutSession,
        onSuccess: () => {
            useSessionStore.getState().clearBootstrap()
            useSessionStore.getState().setRole('student')
            queryClient.clear()
        },
    })
}

export function useSsoProviderMetadataQuery(params?: { enabled?: boolean }) {
    return useQuery({
        queryKey: ['auth', 'sso-provider-metadata'],
        queryFn: getSsoProviderMetadata,
        enabled: params?.enabled ?? true,
        staleTime: 5 * 60 * 1000,
    })
}
