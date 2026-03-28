import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { ShieldAlert, Users } from 'lucide-react'
import { toast } from 'sonner'
import {
    formatAdminScope,
    getAdminRoleTone,
    getAdminStatusTone,
    getComplianceTone,
} from '@/entities/admin/presentation'
import { useAdminUserPatchMutation, useAdminUsersQuery } from '@/entities/admin/queries'
import type { AdminUser, AdminUserScope, AdminUserStatus } from '@/entities/admin/types'
import type { Role } from '@/entities/auth/types'
import { formatDateTime } from '@/shared/lib/format'
import { Badge, Button, Card, FilterBar, Select } from '@/shared/ui'
import { DataTable } from '@/shared/ui/composites/DataTable'

type RoleFilter = 'all' | Role
type ComplianceFilter = 'all' | 'compliant' | 'non_compliant'
type StatusFilter = 'all' | AdminUserStatus

interface UserDraft {
    role: Role
    scope: AdminUserScope
    status: AdminUserStatus
}

const roleOptions = [
    { label: 'All roles', value: 'all' },
    { label: 'Student', value: 'student' },
    { label: 'Lecturer', value: 'lecturer' },
    { label: 'Operator', value: 'operator' },
    { label: 'Admin', value: 'admin' },
]

const editableRoleOptions = roleOptions.filter((option) => option.value !== 'all')

const complianceOptions = [
    { label: 'All domain states', value: 'all' },
    { label: 'Compliant only', value: 'compliant' },
    { label: 'Non-compliant only', value: 'non_compliant' },
]

const statusOptions = [
    { label: 'All statuses', value: 'all' },
    { label: 'Active', value: 'active' },
    { label: 'Invited', value: 'invited' },
    { label: 'Suspended', value: 'suspended' },
]

const editableStatusOptions = statusOptions.filter((option) => option.value !== 'all')

const scopeOptions = [
    { label: 'Student portal', value: 'student_portal' },
    { label: 'Contributor portal', value: 'contributor_portal' },
    { label: 'Operator portal', value: 'operator_portal' },
    { label: 'Admin console', value: 'admin_console' },
]

function isDraftDirty(user: AdminUser, draft?: UserDraft) {
    if (!draft) {
        return false
    }

    return draft.role !== user.role || draft.scope !== user.scope || draft.status !== user.status
}

export function AdminUsersPanel({ scenario }: { scenario?: string }) {
    const usersQuery = useAdminUsersQuery({ scenario })
    const adminUserPatchMutation = useAdminUserPatchMutation({ scenario })
    const [searchValue, setSearchValue] = useState('')
    const [roleFilter, setRoleFilter] = useState<RoleFilter>('all')
    const [complianceFilter, setComplianceFilter] = useState<ComplianceFilter>('all')
    const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
    const [drafts, setDrafts] = useState<Record<string, UserDraft>>({})
    const deferredSearch = useDeferredValue(searchValue)

    useEffect(() => {
        if (!usersQuery.data) {
            return
        }

        setDrafts(
            Object.fromEntries(
                usersQuery.data.map((user) => [
                    user.id,
                    {
                        role: user.role,
                        scope: user.scope,
                        status: user.status,
                    },
                ]),
            ),
        )
    }, [usersQuery.data])

    const filteredUsers = useMemo(() => {
        const normalizedSearch = deferredSearch.trim().toLowerCase()

        return (usersQuery.data ?? []).filter((user) => {
            const matchesSearch =
                normalizedSearch.length === 0 ||
                user.name.toLowerCase().includes(normalizedSearch) ||
                user.email.toLowerCase().includes(normalizedSearch)

            const matchesRole = roleFilter === 'all' || user.role === roleFilter
            const matchesStatus = statusFilter === 'all' || user.status === statusFilter
            const matchesCompliance =
                complianceFilter === 'all' ||
                (complianceFilter === 'compliant' && user.isInternalDomainCompliant) ||
                (complianceFilter === 'non_compliant' && !user.isInternalDomainCompliant)

            return matchesSearch && matchesRole && matchesStatus && matchesCompliance
        })
    }, [complianceFilter, deferredSearch, roleFilter, statusFilter, usersQuery.data])

    const users = usersQuery.data ?? []
    const nonCompliantUsers = users.filter((user) => !user.isInternalDomainCompliant)

    const updateDraft = <TKey extends keyof UserDraft>(userId: string, key: TKey, value: UserDraft[TKey]) => {
        setDrafts((current) => ({
            ...current,
            [userId]: {
                ...(current[userId] ?? {
                    role: 'student',
                    scope: 'student_portal',
                    status: 'active',
                }),
                [key]: value,
            },
        }))
    }

    const handleSave = async (user: AdminUser) => {
        const draft = drafts[user.id]
        if (!draft || !isDraftDirty(user, draft)) {
            return
        }

        try {
            const updatedUser = await adminUserPatchMutation.mutateAsync({
                id: user.id,
                payload: {
                    role: draft.role,
                    scope: draft.scope,
                    status: draft.status,
                },
            })

            toast.success(`Updated ${updatedUser.name}`, {
                description: `${updatedUser.role} / ${formatAdminScope(updatedUser.scope)} / ${updatedUser.status}`,
            })
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Unable to update the selected user.'
            toast.error('User update failed', { description: message })
        }
    }

    if (usersQuery.isError) {
        return <Card className="text-sm text-error-700 dark:text-error-300">{usersQuery.error.message}</Card>
    }

    return (
        <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-4">
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Managed users</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">{users.length}</div>
                </Card>
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Contributor roles</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">
                        {users.filter((user) => ['lecturer', 'operator', 'admin'].includes(user.role)).length}
                    </div>
                </Card>
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Pending invites</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">
                        {users.filter((user) => user.status === 'invited').length}
                    </div>
                </Card>
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Domain exceptions</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">{nonCompliantUsers.length}</div>
                </Card>
            </div>

            <Card className="space-y-2 border-brand-200 bg-brand-50 dark:border-brand-900 dark:bg-brand-950">
                <div className="text-sm font-semibold text-brand-800 dark:text-brand-200">Internal account policy</div>
                <p className="text-sm text-brand-700 dark:text-brand-300">
                    Lecturer, operator and admin roles must use the `@gm.uit.edu.vn` domain. Frontend guards block non-compliant sessions, and this panel lets admins correct role, scope and status without leaving the console.
                </p>
            </Card>

            {nonCompliantUsers.length > 0 ? (
                <Card className="space-y-3 border-error-200 bg-error-50 dark:border-error-800 dark:bg-error-950">
                    <div className="flex items-center gap-2 text-sm font-semibold text-error-700 dark:text-error-200">
                        <ShieldAlert size={16} />
                        Domain compliance issues
                    </div>
                    <div className="space-y-2 text-sm text-error-700 dark:text-error-200">
                        {nonCompliantUsers.map((user) => (
                            <div key={user.id}>
                                {user.name} ({user.email}) is assigned to {user.role} but does not satisfy the institutional domain rule.
                            </div>
                        ))}
                    </div>
                </Card>
            ) : null}

            <FilterBar
                searchValue={searchValue}
                onSearchChange={setSearchValue}
                searchPlaceholder="Search by name or email..."
                actions={
                    <>
                        <div className="min-w-48">
                            <Select
                                aria-label="Filter users by role"
                                options={roleOptions}
                                value={roleFilter}
                                onChange={(event) => setRoleFilter(event.target.value as RoleFilter)}
                            />
                        </div>
                        <div className="min-w-48">
                            <Select
                                aria-label="Filter users by status"
                                options={statusOptions}
                                value={statusFilter}
                                onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
                            />
                        </div>
                        <div className="min-w-52">
                            <Select
                                aria-label="Filter users by internal domain compliance"
                                options={complianceOptions}
                                value={complianceFilter}
                                onChange={(event) => setComplianceFilter(event.target.value as ComplianceFilter)}
                            />
                        </div>
                    </>
                }
            />

            <DataTable
                rows={filteredUsers}
                getRowKey={(user) => user.id}
                isLoading={usersQuery.isLoading}
                emptyIcon={Users}
                emptyTitle="No admin users found"
                emptyDescription="Try a broader search or reset the admin filters."
                columns={[
                    {
                        key: 'identity',
                        header: 'User',
                        render: (user: AdminUser) => (
                            <div className="space-y-1">
                                <div className="font-medium text-gray-900 dark:text-white">{user.name}</div>
                                <div className="text-xs text-gray-500">{user.email}</div>
                            </div>
                        ),
                    },
                    {
                        key: 'role',
                        header: 'Role',
                        render: (user: AdminUser) => (
                            <div className="space-y-2">
                                <Badge tone={getAdminRoleTone(user.role)}>{user.role}</Badge>
                                <Select
                                    aria-label={`Change role for ${user.name}`}
                                    options={editableRoleOptions}
                                    value={drafts[user.id]?.role ?? user.role}
                                    onChange={(event) => updateDraft(user.id, 'role', event.target.value as Role)}
                                />
                            </div>
                        ),
                    },
                    {
                        key: 'scope',
                        header: 'Scope',
                        render: (user: AdminUser) => (
                            <div className="space-y-2">
                                <div className="text-sm text-gray-700 dark:text-gray-200">{formatAdminScope(user.scope)}</div>
                                <Select
                                    aria-label={`Change scope for ${user.name}`}
                                    options={scopeOptions}
                                    value={drafts[user.id]?.scope ?? user.scope}
                                    onChange={(event) => updateDraft(user.id, 'scope', event.target.value as AdminUserScope)}
                                />
                            </div>
                        ),
                    },
                    {
                        key: 'status',
                        header: 'Status',
                        render: (user: AdminUser) => (
                            <div className="space-y-2">
                                <Badge tone={getAdminStatusTone(user.status)}>{user.status}</Badge>
                                <Select
                                    aria-label={`Change status for ${user.name}`}
                                    options={editableStatusOptions}
                                    value={drafts[user.id]?.status ?? user.status}
                                    onChange={(event) => updateDraft(user.id, 'status', event.target.value as AdminUserStatus)}
                                />
                            </div>
                        ),
                    },
                    {
                        key: 'compliance',
                        header: 'Domain compliance',
                        render: (user: AdminUser) => (
                            <Badge tone={getComplianceTone(user.isInternalDomainCompliant)}>
                                {user.isInternalDomainCompliant ? 'Compliant' : 'Needs review'}
                            </Badge>
                        ),
                    },
                    {
                        key: 'lastActive',
                        header: 'Last active',
                        render: (user: AdminUser) => formatDateTime(user.lastActiveAt),
                    },
                    {
                        key: 'actions',
                        header: 'Action',
                        render: (user: AdminUser) => {
                            const draft = drafts[user.id]
                            const dirty = isDraftDirty(user, draft)
                            const isSaving = adminUserPatchMutation.isPending && adminUserPatchMutation.variables?.id === user.id

                            return (
                                <div className="flex flex-col gap-2">
                                    <Button
                                        size="sm"
                                        variant={dirty ? 'primary' : 'secondary'}
                                        isLoading={isSaving}
                                        disabled={!dirty}
                                        onClick={() => void handleSave(user)}
                                    >
                                        Save
                                    </Button>
                                    <span className="text-xs text-gray-500">{dirty ? 'Unsaved changes' : 'In sync'}</span>
                                </div>
                            )
                        },
                    },
                ]}
            />
        </div>
    )
}
