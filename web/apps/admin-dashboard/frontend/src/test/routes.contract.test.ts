import { describe, expect, it } from 'vitest'
import {
    INTERNAL_EMAIL_DOMAIN,
    canAccessPath,
    canAccessSessionPath,
    getDefaultPathForRole,
    getExperienceRole,
    getExperienceRoleLabel,
    getRouteMeta,
    internalRoles,
} from '@/app/config/routes'
import type { Role, Session } from '@/entities/auth/types'

function buildSession(role: Role, email: string): Session {
    return {
        id: `session-${role}`,
        status: 'authenticated',
        user: {
            id: `user-${role}`,
            name: `Test ${role}`,
            email,
            role,
            department: 'Test',
            avatarInitials: 'TS',
        },
    }
}

describe('route contract', () => {
    it('resolves stable route metadata', () => {
        expect(getRouteMeta('/documents')?.title).toBe('Tài liệu')
        expect(getRouteMeta('/library')?.title).toBe('Tài liệu')
        expect(getRouteMeta('/upload')?.title).toBe('Tải lên')
        expect(getRouteMeta('/manager')?.shell).toBe('app')
        expect(getRouteMeta('/documents/doc-001')?.shell).toBe('app')
        expect(getRouteMeta('/auth/callback')?.shell).toBe('auth')
        expect(getRouteMeta('/unknown-route')).toBeUndefined()
    })

    it('enforces role access matrix', () => {
        expect(canAccessPath('student', '/')).toBe(true)
        expect(canAccessPath('student', '/chat')).toBe(true)
        expect(canAccessPath('student', '/documents')).toBe(true)
        expect(canAccessPath('teacher', '/upload')).toBe(true)
        expect(canAccessPath('teacher', '/manager')).toBe(false)
        expect(canAccessPath('admin', '/auth/login')).toBe(true)
        expect(canAccessPath('admin', '/manager')).toBe(true)
        expect(canAccessPath('student', '/manager')).toBe(false)
        expect(canAccessPath('student', '/preview/custom')).toBe(true)
    })

    it('enforces internal email requirements on session-aware access checks', () => {
        expect(canAccessSessionPath(buildSession('teacher', `teacher${INTERNAL_EMAIL_DOMAIN}`), '/upload')).toBe(true)
        expect(canAccessSessionPath(buildSession('teacher', 'teacher@gmail.com'), '/upload')).toBe(false)
        expect(canAccessSessionPath(buildSession('admin', `admin${INTERNAL_EMAIL_DOMAIN}`), '/manager')).toBe(true)
        expect(canAccessSessionPath(buildSession('admin', 'admin@gmail.com'), '/manager')).toBe(false)
        expect(canAccessSessionPath(buildSession('student', 'student@gm.uit.edu.vn'), '/chat')).toBe(true)
    })

    it('returns stable experience labels and default route helpers', () => {
        expect(getExperienceRole('student')).toBe('student')
        expect(getExperienceRole('teacher')).toBe('teacher')
        expect(getExperienceRole('admin')).toBe('admin')

        expect(getExperienceRoleLabel('student')).toBe('Sinh viên')
        expect(getExperienceRoleLabel('teacher')).toBe('Giảng viên')
        expect(getExperienceRoleLabel('admin')).toBe('Quản trị viên')

        expect(getDefaultPathForRole('student')).toBe('/chat')
        expect(getDefaultPathForRole('teacher')).toBe('/chat')
        expect(getDefaultPathForRole('admin')).toBe('/chat')
        expect(internalRoles).toEqual(['teacher', 'admin'])
    })
})
