import type { Role, RoleDto } from '@/entities/auth/types'

export const appRoles: Role[] = ['student', 'teacher', 'admin']

const roleNormalizationMap: Record<RoleDto, Role> = {
    guest: 'student',
    student: 'student',
    teacher: 'teacher',
    lecturer: 'teacher',
    operator: 'admin',
    admin: 'admin',
}

export function isRole(value: unknown): value is Role {
    return typeof value === 'string' && appRoles.includes(value as Role)
}

export function isRoleDto(value: unknown): value is RoleDto {
    return typeof value === 'string' && value in roleNormalizationMap
}

export function normalizeRole(role: Role | RoleDto): Role {
    return roleNormalizationMap[role]
}

export function serializeRole(role: Role): Extract<RoleDto, 'student' | 'teacher' | 'admin'> {
    return role
}

export function isInternalRole(role: Role) {
    return role === 'teacher' || role === 'admin'
}
