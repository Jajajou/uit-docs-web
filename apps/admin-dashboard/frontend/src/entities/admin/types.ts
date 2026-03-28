import type { Role } from '@/entities/auth/types'

export type AdminShellScope = 'public' | 'auth' | 'portal' | 'admin' | 'system'
export type AdminUserStatus = 'active' | 'invited' | 'suspended'
export type AdminUserScope = 'student_portal' | 'contributor_portal' | 'operator_portal' | 'admin_console'
export type SystemSettingGroup = 'auth' | 'ingestion' | 'publication' | 'chat'
export type SystemSettingSource = 'derived_contract' | 'mock_policy'
export type AuditActionType =
    | 'upload_submission'
    | 'approve_review'
    | 'reject_review'
    | 'request_changes'
    | 'archive_document'
    | 'reindex_document'
    | 'login'
    | 'role_switch'
export type AuditTargetType = 'submission' | 'review' | 'document' | 'session'

export interface AdminUser {
    id: string
    name: string
    email: string
    role: Role
    status: AdminUserStatus
    scope: AdminUserScope
    lastActiveAt: string
    isInternalDomainCompliant: boolean
}

export interface RolePolicy {
    role: Role
    allowedShells: AdminShellScope[]
    allowedRoutes: string[]
    requiresInternalEmail: boolean
}

export interface SystemSetting {
    group: SystemSettingGroup
    key: string
    label: string
    value: string
    description: string
    isSensitive: boolean
    source: SystemSettingSource
}

export interface AuditLogEntry {
    id: string
    actorName: string
    actorRole: Role
    action: AuditActionType
    targetType: AuditTargetType
    targetId: string
    targetLabel: string
    createdAt: string
}

export interface AdminUserDto {
    id: string
    name: string
    email: string
    role: Role
    status: AdminUserStatus
    scope: AdminUserScope
    last_active_at: string
    is_internal_domain_compliant: boolean
}

export interface RolePolicyDto {
    role: Role
    allowed_shells: AdminShellScope[]
    allowed_routes: string[]
    requires_internal_email: boolean
}

export interface SystemSettingDto {
    group: SystemSettingGroup
    key: string
    label: string
    value: string
    description: string
    is_sensitive: boolean
    source: SystemSettingSource
}

export interface AuditLogEntryDto {
    id: string
    actor_name: string
    actor_role: Role
    action: AuditActionType
    target_type: AuditTargetType
    target_id: string
    target_label: string
    created_at: string
}

export interface AdminUserPatchInput {
    role?: Role
    status?: AdminUserStatus
    scope?: AdminUserScope
}

export interface SystemSettingPatchInput {
    value: string
}
