import { internalRoles, routeMeta } from '@/app/config/routes'
import type {
    AdminUserDto,
    AuditLogEntryDto,
    RolePolicyDto,
    SystemSettingDto,
} from '@/entities/admin/types'
import type { Role } from '@/entities/auth/types'

const roleOrder: Role[] = ['student', 'teacher', 'admin']

export const adminUserFixtures: AdminUserDto[] = [
    {
        id: 'usr-001',
        name: 'Nguyen Minh Student',
        email: 'student@gm.uit.edu.vn',
        role: 'student',
        status: 'active',
        scope: 'student_portal',
        last_active_at: '2026-03-20T07:10:00.000Z',
        is_internal_domain_compliant: true,
    },
    {
        id: 'usr-002',
        name: 'Pham Van Teacher',
        email: 'teacher@gm.uit.edu.vn',
        role: 'teacher',
        status: 'active',
        scope: 'teacher_workspace',
        last_active_at: '2026-03-20T06:42:00.000Z',
        is_internal_domain_compliant: true,
    },
    {
        id: 'usr-003',
        name: 'Tran Thi Admin Support',
        email: 'admin-support@gm.uit.edu.vn',
        role: 'admin',
        status: 'active',
        scope: 'admin_console',
        last_active_at: '2026-03-20T06:58:00.000Z',
        is_internal_domain_compliant: true,
    },
    {
        id: 'usr-004',
        name: 'Tran Van Admin',
        email: 'admin@gm.uit.edu.vn',
        role: 'admin',
        status: 'active',
        scope: 'admin_console',
        last_active_at: '2026-03-20T05:55:00.000Z',
        is_internal_domain_compliant: true,
    },
    {
        id: 'usr-005',
        name: 'Invite Pending Teacher',
        email: 'pending-teacher@gm.uit.edu.vn',
        role: 'teacher',
        status: 'invited',
        scope: 'teacher_workspace',
        last_active_at: '2026-03-18T02:10:00.000Z',
        is_internal_domain_compliant: true,
    },
]

export const nonCompliantAdminUserFixtures: AdminUserDto[] = adminUserFixtures.map((user) =>
    user.id === 'usr-005'
        ? {
            ...user,
            email: 'pending-teacher@gmail.com',
            is_internal_domain_compliant: false,
        }
        : user,
)

function buildRolePolicy(role: Role): RolePolicyDto {
    const allowedRoutes = routeMeta
        .filter((route) => route.allowedRoles.includes(role))
        .map((route) => route.path)

    const allowedShells = [...new Set(routeMeta.filter((route) => route.allowedRoles.includes(role)).map((route) => route.shell))]

    return {
        role,
        allowed_shells: allowedShells,
        allowed_routes: allowedRoutes,
        requires_internal_email: internalRoles.includes(role),
    }
}

export const rolePolicyFixtures: RolePolicyDto[] = roleOrder.map(buildRolePolicy)

export const systemSettingFixtures: SystemSettingDto[] = [
    {
        group: 'auth',
        key: 'sso_provider',
        label: 'Teacher SSO provider',
        value: 'UIT Google Workspace SSO',
        description: 'Internal staff accounts must authenticate via institutional SSO.',
        is_sensitive: false,
        source: 'mock_policy',
    },
    {
        group: 'auth',
        key: 'internal_domain_rule',
        label: 'Internal domain rule',
        value: '@gm.uit.edu.vn required for teacher/admin',
        description: 'Teacher and admin roles are valid only with the institutional mail domain.',
        is_sensitive: false,
        source: 'derived_contract',
    },
    {
        group: 'ingestion',
        key: 'publication_gate',
        label: 'Publication gate',
        value: 'Review approval required before public release',
        description: 'Teacher uploads remain provisional until the admin review step approves them.',
        is_sensitive: false,
        source: 'derived_contract',
    },
    {
        group: 'publication',
        key: 'admin_break_glass_override',
        label: 'Admin control ownership',
        value: 'Admin executes review and remediation actions with explicit audit trail',
        description: 'Archive, reindex, retry and review decisions remain admin-owned and auditable.',
        is_sensitive: false,
        source: 'derived_contract',
    },
    {
        group: 'publication',
        key: 'system_api_key',
        label: 'Backend ingestion secret',
        value: 'stored-in-secret-manager',
        description: 'Credentials are managed server-side and never shown in frontend cleartext.',
        is_sensitive: true,
        source: 'mock_policy',
    },
    {
        group: 'chat',
        key: 'citation_policy',
        label: 'Citation policy',
        value: 'Student-facing answers must display references and warnings',
        description: 'Low-confidence, pending-review or archived sources require explicit UI warnings.',
        is_sensitive: false,
        source: 'derived_contract',
    },
]

export const auditLogFixtures: AuditLogEntryDto[] = [
    {
        id: 'audit-001',
        actor_name: 'Pham Van Teacher',
        actor_role: 'teacher',
        action: 'upload_submission',
        target_type: 'submission',
        target_id: 'sub-002',
        target_label: 'Thong bao lich dang ky mon hoc',
        created_at: '2026-03-17T05:05:00.000Z',
    },
    {
        id: 'audit-002',
        actor_name: 'Tran Van Admin',
        actor_role: 'admin',
        action: 'approve_review',
        target_type: 'review',
        target_id: 'review-002',
        target_label: 'Thong bao lich dang ky mon hoc',
        created_at: '2026-03-17T05:31:00.000Z',
    },
    {
        id: 'audit-003',
        actor_name: 'Tran Van Admin',
        actor_role: 'admin',
        action: 'approve_review',
        target_type: 'document',
        target_id: 'doc-004',
        target_label: 'Thong bao lich dang ky mon hoc',
        created_at: '2026-03-17T05:33:00.000Z',
    },
    {
        id: 'audit-004',
        actor_name: 'Tran Van Admin',
        actor_role: 'admin',
        action: 'archive_document',
        target_type: 'document',
        target_id: 'doc-003',
        target_label: 'Thong bao hoc bong doanh nghiep',
        created_at: '2026-02-01T09:20:00.000Z',
    },
    {
        id: 'audit-004b',
        actor_name: 'Tran Van Admin',
        actor_role: 'admin',
        action: 'reindex_document',
        target_type: 'document',
        target_id: 'doc-002',
        target_label: 'Thong bao hoc phi hoc ky 2',
        created_at: '2026-03-18T04:17:00.000Z',
    },
    {
        id: 'audit-005',
        actor_name: 'Tran Van Admin',
        actor_role: 'admin',
        action: 'role_switch',
        target_type: 'session',
        target_id: 'session-admin',
        target_label: 'Demo role switch to admin',
        created_at: '2026-03-20T07:30:00.000Z',
    },
]

export const denseAuditLogFixtures: AuditLogEntryDto[] = [
    {
        id: 'audit-000',
        actor_name: 'Nguyen Minh Student',
        actor_role: 'student',
        action: 'login',
        target_type: 'session',
        target_id: 'session-student',
        target_label: 'Student portal session',
        created_at: '2026-03-20T06:15:00.000Z',
    },
    ...auditLogFixtures,
    {
        id: 'audit-006',
        actor_name: 'Tran Van Admin',
        actor_role: 'admin',
        action: 'reject_review',
        target_type: 'review',
        target_id: 'review-003',
        target_label: 'Thong bao hoc phi hoc ky 2',
        created_at: '2026-03-18T16:15:00.000Z',
    },
]
