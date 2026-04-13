import type {
    AdminUser,
    AdminUserScope,
    AdminUserStatus,
    AuditActionType,
    AuditLogEntry,
    RolePolicy,
    SystemSetting,
    SystemSettingGroup,
} from '@/entities/admin/types'

type BadgeTone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger'

export function getAdminRoleTone(role: AdminUser['role']): BadgeTone {
    switch (role) {
        case 'admin':
            return 'danger'
        case 'teacher':
            return 'success'
        case 'student':
            return 'neutral'
        default:
            return 'warning'
    }
}

export function getAdminStatusTone(status: AdminUserStatus): BadgeTone {
    switch (status) {
        case 'active':
            return 'success'
        case 'invited':
            return 'warning'
        case 'suspended':
            return 'danger'
        default:
            return 'neutral'
    }
}

export function getComplianceTone(isCompliant: boolean): BadgeTone {
    return isCompliant ? 'success' : 'danger'
}

export function formatAdminScope(scope: AdminUserScope) {
    return scope.replace(/_/g, ' ')
}

export function formatSettingGroup(group: SystemSettingGroup) {
    return group.replace(/_/g, ' ')
}

export function formatAuditAction(action: AuditActionType) {
    return action.replace(/_/g, ' ')
}

export function maskSettingValue(setting: SystemSetting) {
    return setting.isSensitive ? 'Managed securely server-side' : setting.value
}

export function getPolicyShellSummary(policy: RolePolicy) {
    return policy.allowedShells.map((shell) => shell.replace(/_/g, ' ')).join(', ')
}

export function getAuditTargetPath(entry: AuditLogEntry) {
    if (entry.targetType === 'submission') {
        return `/portal/submissions/${entry.targetId}`
    }

    if (entry.targetType === 'document') {
        return `/documents/${entry.targetId}`
    }

    if (entry.targetType === 'review') {
        return '/portal/review'
    }

    return null
}
