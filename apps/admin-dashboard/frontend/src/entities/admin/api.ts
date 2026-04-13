import { apiClient } from '@/shared/api/client'
import {
    mapAdminUserDtoToAdminUser,
    mapAuditLogEntryDtoToAuditLogEntry,
    mapRolePolicyDtoToRolePolicy,
    mapSystemSettingDtoToSystemSetting,
} from '@/entities/admin/mappers'
import { serializeRole } from '@/entities/auth/roles'
import type {
    AdminUserPatchInput,
    AdminUser,
    AdminUserDto,
    AuditLogEntry,
    AuditLogEntryDto,
    RolePolicy,
    RolePolicyDto,
    SystemSettingPatchInput,
    SystemSetting,
    SystemSettingDto,
} from '@/entities/admin/types'

export async function getAdminUsers(params?: { scenario?: string }): Promise<AdminUser[]> {
    const response = await apiClient.get<{ users: AdminUserDto[] }>('/admin/users', {
        params,
    })

    return response.data.users.map(mapAdminUserDtoToAdminUser)
}

export async function getRolePolicies(params?: { scenario?: string }): Promise<RolePolicy[]> {
    const response = await apiClient.get<{ roles: RolePolicyDto[] }>('/admin/roles', {
        params,
    })

    return response.data.roles.map(mapRolePolicyDtoToRolePolicy)
}

export async function getSystemSettings(params?: { scenario?: string }): Promise<SystemSetting[]> {
    const response = await apiClient.get<{ settings: SystemSettingDto[] }>('/admin/settings', {
        params,
    })

    return response.data.settings.map(mapSystemSettingDtoToSystemSetting)
}

export async function getAuditLogs(params?: { scenario?: string }): Promise<AuditLogEntry[]> {
    const response = await apiClient.get<{ logs: AuditLogEntryDto[] }>('/admin/audit-logs', {
        params,
    })

    return response.data.logs.map(mapAuditLogEntryDtoToAuditLogEntry)
}

export async function patchAdminUser(id: string, payload: AdminUserPatchInput, params?: { scenario?: string }): Promise<AdminUser> {
    const requestPayload = {
        ...payload,
        role: payload.role ? serializeRole(payload.role) : undefined,
    }

    const response = await apiClient.patch<{ user: AdminUserDto }>(`/admin/users/${id}`, requestPayload, {
        params,
    })

    return mapAdminUserDtoToAdminUser(response.data.user)
}

export async function patchSystemSetting(
    key: string,
    payload: SystemSettingPatchInput,
    params?: { scenario?: string },
): Promise<SystemSetting> {
    const response = await apiClient.patch<{ setting: SystemSettingDto }>(`/admin/settings/${key}`, payload, {
        params,
    })

    return mapSystemSettingDtoToSystemSetting(response.data.setting)
}
