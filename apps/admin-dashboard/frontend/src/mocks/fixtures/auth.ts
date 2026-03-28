import type { Role, SessionDto } from '@/entities/auth/types'

function buildSession(role: Role): SessionDto {
    if (role === 'guest') {
        return {
            session_id: 'session-guest',
            status: 'anonymous',
            user: {
                id: 'guest',
                name: 'Guest User',
                email: 'guest@public.uit.edu.vn',
                role,
                department: 'Public',
                avatar_initials: 'GU',
            },
        }
    }

    const identityByRole: Record<Exclude<Role, 'guest'>, Omit<SessionDto['user'], 'role'>> = {
        student: {
            id: 'user-student',
            name: 'Nguyen Thi Student',
            email: 'student@uit.edu.vn',
            department: 'Student',
            avatar_initials: 'NS',
        },
        lecturer: {
            id: 'user-lecturer',
            name: 'Pham Van Lecturer',
            email: 'lecturer@gm.uit.edu.vn',
            department: 'Faculty of Computer Science',
            avatar_initials: 'PL',
        },
        operator: {
            id: 'user-operator',
            name: 'Le Thi Operator',
            email: 'operator@gm.uit.edu.vn',
            department: 'Knowledge Operations',
            avatar_initials: 'LO',
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
    guest: buildSession('guest'),
    student: buildSession('student'),
    lecturer: buildSession('lecturer'),
    operator: buildSession('operator'),
    admin: buildSession('admin'),
}
