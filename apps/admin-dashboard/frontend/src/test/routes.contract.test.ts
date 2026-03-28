import { describe, expect, it } from 'vitest'
import { INTERNAL_EMAIL_DOMAIN, canAccessPath, canAccessSessionPath, getRouteMeta } from '@/app/config/routes'
import type { Role, Session } from '@/entities/auth/types'

function buildSession(role: Role, email: string): Session {
    return {
        id: `session-${role}`,
        status: role === 'guest' ? 'anonymous' : 'authenticated',
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
        expect(getRouteMeta('/portal/upload')?.title).toBe('Upload')
        expect(getRouteMeta('/admin/users')?.shell).toBe('admin')
        expect(getRouteMeta('/documents/doc-001')?.shell).toBe('public')
    })

    it('enforces role access matrix', () => {
        expect(canAccessPath('guest', '/')).toBe(true)
        expect(canAccessPath('student', '/chat')).toBe(true)
        expect(canAccessPath('lecturer', '/portal/upload')).toBe(true)
        expect(canAccessPath('lecturer', '/portal/review')).toBe(false)
        expect(canAccessPath('operator', '/portal/jobs')).toBe(true)
        expect(canAccessPath('operator', '/admin/users')).toBe(false)
        expect(canAccessPath('admin', '/admin/settings')).toBe(true)
        expect(canAccessPath('guest', '/admin/users')).toBe(false)
    })

    it('enforces internal email requirements on session-aware access checks', () => {
        expect(canAccessSessionPath(buildSession('lecturer', `lecturer${INTERNAL_EMAIL_DOMAIN}`), '/portal/upload')).toBe(true)
        expect(canAccessSessionPath(buildSession('lecturer', 'lecturer@uit.edu.vn'), '/portal/upload')).toBe(false)
        expect(canAccessSessionPath(buildSession('admin', `admin${INTERNAL_EMAIL_DOMAIN}`), '/admin/settings')).toBe(true)
        expect(canAccessSessionPath(buildSession('admin', 'admin@uit.edu.vn'), '/admin/settings')).toBe(false)
        expect(canAccessSessionPath(buildSession('student', 'student@uit.edu.vn'), '/chat')).toBe(true)
    })
})
