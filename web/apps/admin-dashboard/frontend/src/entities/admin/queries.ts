import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getAdminUsers, getAuditLogs, getRolePolicies, getSystemSettings, patchAdminUser, patchSystemSetting } from '@/entities/admin/api'
import type { AdminUser, AdminUserPatchInput, SystemSetting, SystemSettingPatchInput } from '@/entities/admin/types'

export function useAdminUsersQuery(params?: { scenario?: string }) {
    return useQuery({
        queryKey: ['admin-users', params?.scenario ?? 'happy'],
        queryFn: () => getAdminUsers(params),
    })
}

export function useRolePoliciesQuery(params?: { scenario?: string }) {
    return useQuery({
        queryKey: ['role-policies', params?.scenario ?? 'happy'],
        queryFn: () => getRolePolicies(params),
    })
}

export function useSystemSettingsQuery(params?: { scenario?: string }) {
    return useQuery({
        queryKey: ['system-settings', params?.scenario ?? 'happy'],
        queryFn: () => getSystemSettings(params),
    })
}

export function useAuditLogsQuery(params?: { scenario?: string }) {
    return useQuery({
        queryKey: ['audit-logs', params?.scenario ?? 'happy'],
        queryFn: () => getAuditLogs(params),
    })
}

export function useAdminUserPatchMutation(params?: { scenario?: string }) {
    const queryClient = useQueryClient()
    const scenarioKey = params?.scenario ?? 'happy'

    return useMutation({
        mutationFn: ({ id, payload }: { id: string; payload: AdminUserPatchInput }) => patchAdminUser(id, payload, params),
        onSuccess: (user) => {
            queryClient.setQueryData(['admin-users', scenarioKey], (current: AdminUser[] | undefined) =>
                (current ?? []).map((entry) => (entry.id === user.id ? user : entry)),
            )
        },
    })
}

export function useSystemSettingPatchMutation(params?: { scenario?: string }) {
    const queryClient = useQueryClient()
    const scenarioKey = params?.scenario ?? 'happy'

    return useMutation({
        mutationFn: ({ key, payload }: { key: string; payload: SystemSettingPatchInput }) => patchSystemSetting(key, payload, params),
        onSuccess: (setting) => {
            queryClient.setQueryData(['system-settings', scenarioKey], (current: SystemSetting[] | undefined) =>
                (current ?? []).map((entry) => (entry.key === setting.key ? setting : entry)),
            )
        },
    })
}
