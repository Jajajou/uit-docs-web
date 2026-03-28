import type {
    AdminUser,
    AdminUserDto,
    RolePolicy,
    RolePolicyDto,
    SystemSetting,
    SystemSettingDto,
    AuditLogEntry,
    AuditLogEntryDto,
} from '@/entities/admin/types'

export function mapAdminUserDtoToAdminUser(dto: AdminUserDto): AdminUser {
    return {
        id: dto.id,
        name: dto.name,
        email: dto.email,
        role: dto.role,
        status: dto.status,
        scope: dto.scope,
        lastActiveAt: dto.last_active_at,
        isInternalDomainCompliant: dto.is_internal_domain_compliant,
    }
}

export function mapRolePolicyDtoToRolePolicy(dto: RolePolicyDto): RolePolicy {
    return {
        role: dto.role,
        allowedShells: dto.allowed_shells,
        allowedRoutes: dto.allowed_routes,
        requiresInternalEmail: dto.requires_internal_email,
    }
}

export function mapSystemSettingDtoToSystemSetting(dto: SystemSettingDto): SystemSetting {
    return {
        group: dto.group,
        key: dto.key,
        label: dto.label,
        value: dto.value,
        description: dto.description,
        isSensitive: dto.is_sensitive,
        source: dto.source,
    }
}

export function mapAuditLogEntryDtoToAuditLogEntry(dto: AuditLogEntryDto): AuditLogEntry {
    return {
        id: dto.id,
        actorName: dto.actor_name,
        actorRole: dto.actor_role,
        action: dto.action,
        targetType: dto.target_type,
        targetId: dto.target_id,
        targetLabel: dto.target_label,
        createdAt: dto.created_at,
    }
}
