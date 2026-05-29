import type { Role, SessionDto } from '@/entities/auth/types'

function buildSession(role: Role): SessionDto {
    const identityByRole: Record<Role, Omit<SessionDto['user'], 'role'>> = {
        student: {
            id: 'user-student',
            name: 'Nguyen Thi Student',
            email: 'student@gm.uit.edu.vn',
            department: 'Student',
            avatar_initials: 'NS',
        },
        teacher: {
            id: 'user-teacher',
            name: 'Pham Van Teacher',
            email: 'teacher@gm.uit.edu.vn',
            department: 'Faculty of Computer Science',
            avatar_initials: 'PT',
        },
        admin: {
            id: 'user-admin',
            name: 'Tran Van Admin',
            email: 'admin@gm.uit.edu.vn',
            department: 'System Administration',
            avatar_initials: 'TA',
        },
    }

    return {
        session_id: `session-${role}`,
        status: 'authenticated',
        user: {
            ...identityByRole[role],
            role,
        },
    }
}

export const sessionFixtures = {
    student: buildSession('student'),
    teacher: buildSession('teacher'),
    admin: buildSession('admin'),
}
