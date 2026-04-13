import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ShieldCheck, Users } from 'lucide-react'
import { toast } from 'sonner'
import { getAdminRoleTone, getAdminStatusTone, getComplianceTone } from '@/entities/admin/presentation'
import { useAdminUserPatchMutation, useAdminUsersQuery } from '@/entities/admin/queries'
import type { AdminUser, AdminUserStatus } from '@/entities/admin/types'
import type { Role } from '@/entities/auth/types'
import { formatDateTime } from '@/shared/lib/format'
import { Badge, Button, Card, FilterBar, Select } from '@/shared/ui'
import { DataTable } from '@/shared/ui/composites/DataTable'

type RoleFilter = 'all' | Role
type ComplianceFilter = 'all' | 'compliant' | 'non_compliant'
type StatusFilter = 'all' | AdminUserStatus

interface UserDraft {
    role: Role
    status: AdminUserStatus
}

const roleOptions = [
    { label: 'Tất cả vai trò', value: 'all' },
    { label: 'Sinh viên', value: 'student' },
    { label: 'Giảng viên', value: 'teacher' },
    { label: 'Quản trị viên', value: 'admin' },
]

const editableRoleOptions = roleOptions.filter((option) => option.value !== 'all')

const complianceOptions = [
    { label: 'Tất cả email', value: 'all' },
    { label: 'Đúng chính sách', value: 'compliant' },
    { label: 'Cần rà soát', value: 'non_compliant' },
]

const statusOptions = [
    { label: 'Tất cả trạng thái', value: 'all' },
    { label: 'Đang hoạt động', value: 'active' },
    { label: 'Đang mời', value: 'invited' },
    { label: 'Tạm khóa', value: 'suspended' },
]

const editableStatusOptions = statusOptions.filter((option) => option.value !== 'all')

const roleLabels: Record<Role, string> = {
    student: 'Sinh viên',
    teacher: 'Giảng viên',
    admin: 'Quản trị viên',
}

const statusLabels: Record<AdminUserStatus, string> = {
    active: 'Đang hoạt động',
    invited: 'Đang mời',
    suspended: 'Tạm khóa',
}

const workspaceLabels: Record<Role, string> = {
    student: 'Chat',
    teacher: 'Chat + Tải lên',
    admin: 'Chat + Tải lên + Quản trị',
}

function isDraftDirty(user: AdminUser, draft?: UserDraft) {
    if (!draft) {
        return false
    }

    return draft.role !== user.role || draft.status !== user.status
}

function MetricCard({ label, value }: { label: string; value: number }) {
    return (
        <Card className="relative overflow-hidden space-y-1 border-white/75 dark:border-brand-400/12 dark:bg-[linear-gradient(180deg,rgba(8,18,31,0.94),rgba(12,24,41,0.96))]">
            <div className="pointer-events-none absolute inset-x-5 top-0 h-px bg-gradient-to-r from-transparent via-brand-300/55 to-transparent dark:via-brand-300/32" />
            <div className="text-sm font-medium text-gray-500 dark:text-slate-300">{label}</div>
            <div className="text-3xl font-semibold text-gray-950 dark:text-white">{value}</div>
        </Card>
    )
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
                    status: draft.status,
                },
            })

            toast.success(`Đã cập nhật ${updatedUser.name}`, {
                description: `${roleLabels[updatedUser.role]} · ${statusLabels[updatedUser.status]}`,
            })
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Không thể cập nhật người dùng đã chọn.'
            toast.error('Cập nhật thất bại', { description: message })
        }
    }

    if (usersQuery.isError) {
        return <Card className="text-sm text-error-700 dark:text-error-300">{usersQuery.error.message}</Card>
    }

    return (
        <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-4">
                <MetricCard label="Tổng tài khoản" value={users.length} />
                <MetricCard label="Role nội bộ" value={users.filter((user) => ['teacher', 'admin'].includes(user.role)).length} />
                <MetricCard label="Đang mời" value={users.filter((user) => user.status === 'invited').length} />
                <MetricCard label="Email cần rà soát" value={nonCompliantUsers.length} />
            </div>

            <Card className="space-y-3 border-brand-200 bg-brand-50/85 dark:border-brand-400/14 dark:bg-[linear-gradient(180deg,rgba(8,19,34,0.9),rgba(10,24,44,0.9))]">
                <div className="flex items-center gap-2 text-sm font-semibold text-brand-800 dark:text-brand-200">
                    <ShieldCheck size={16} />
                    Chính sách vai trò
                </div>
                <p className="text-sm leading-6 text-brand-700 dark:text-brand-200/90">
                    Mọi tài khoản đăng nhập Google lần đầu sẽ được tạo ở role student. Admin dùng bảng dưới để nâng quyền lên teacher hoặc admin, đồng thời có
                    thể khóa hoặc mời lại tài khoản khi cần.
                </p>
            </Card>

            {nonCompliantUsers.length > 0 ? (
                <Card className="space-y-3 border-error-200 bg-error-50/85 dark:border-error-500/18 dark:bg-[linear-gradient(180deg,rgba(36,12,18,0.88),rgba(25,10,15,0.9))]">
                    <div className="flex items-center gap-2 text-sm font-semibold text-error-700 dark:text-error-300">
                        <AlertTriangle size={16} />
                        Tài khoản cần rà soát email
                    </div>
                    <div className="space-y-2 text-sm leading-6 text-error-700 dark:text-error-200/90">
                        {nonCompliantUsers.map((user) => (
                            <div key={user.id}>
                                {user.name} ({user.email}) đang mang role {roleLabels[user.role].toLowerCase()} nhưng chưa đạt yêu cầu email trường.
                            </div>
                        ))}
                    </div>
                </Card>
            ) : null}

            <FilterBar
                searchValue={searchValue}
                onSearchChange={setSearchValue}
                searchPlaceholder="Tìm theo tên hoặc email người dùng..."
                actions={
                    <>
                        <div className="min-w-48">
                            <Select
                                aria-label="Lọc người dùng theo vai trò"
                                className="dark:border-brand-400/18 dark:bg-[linear-gradient(180deg,rgba(9,20,36,0.94),rgba(12,26,45,0.98))]"
                                options={roleOptions}
                                value={roleFilter}
                                onChange={(event) => setRoleFilter(event.target.value as RoleFilter)}
                            />
                        </div>
                        <div className="min-w-48">
                            <Select
                                aria-label="Lọc người dùng theo trạng thái"
                                className="dark:border-brand-400/18 dark:bg-[linear-gradient(180deg,rgba(9,20,36,0.94),rgba(12,26,45,0.98))]"
                                options={statusOptions}
                                value={statusFilter}
                                onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
                            />
                        </div>
                        <div className="min-w-52">
                            <Select
                                aria-label="Lọc người dùng theo trạng thái email"
                                className="dark:border-brand-400/18 dark:bg-[linear-gradient(180deg,rgba(9,20,36,0.94),rgba(12,26,45,0.98))]"
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
                emptyTitle="Không có người dùng phù hợp"
                emptyDescription="Thử nới bộ lọc hoặc xóa từ khóa tìm kiếm."
                columns={[
                    {
                        key: 'identity',
                        header: 'Người dùng',
                        render: (user: AdminUser) => (
                            <div className="space-y-1">
                                <div className="font-semibold text-gray-900 dark:text-white">{user.name}</div>
                                <div className="text-xs text-gray-500 dark:text-slate-400">{user.email}</div>
                            </div>
                        ),
                    },
                    {
                        key: 'workspace',
                        header: 'Quyền truy cập',
                        render: (user: AdminUser) => (
                            <div className="space-y-2">
                                <Badge tone={getAdminRoleTone(user.role)}>{roleLabels[user.role]}</Badge>
                                <div className="text-xs text-gray-500 dark:text-slate-400">{workspaceLabels[user.role]}</div>
                            </div>
                        ),
                    },
                    {
                        key: 'role-editor',
                        header: 'Chỉnh role',
                        render: (user: AdminUser) => (
                            <Select
                                aria-label={`Đổi role cho ${user.name}`}
                                className="dark:border-brand-400/14 dark:bg-[linear-gradient(180deg,rgba(8,18,31,0.94),rgba(11,24,42,0.98))]"
                                options={editableRoleOptions}
                                value={drafts[user.id]?.role ?? user.role}
                                onChange={(event) => updateDraft(user.id, 'role', event.target.value as Role)}
                            />
                        ),
                    },
                    {
                        key: 'status',
                        header: 'Trạng thái',
                        render: (user: AdminUser) => (
                            <div className="space-y-2">
                                <Badge tone={getAdminStatusTone(user.status)}>{statusLabels[user.status]}</Badge>
                                <Select
                                    aria-label={`Đổi trạng thái cho ${user.name}`}
                                    className="dark:border-brand-400/14 dark:bg-[linear-gradient(180deg,rgba(8,18,31,0.94),rgba(11,24,42,0.98))]"
                                    options={editableStatusOptions}
                                    value={drafts[user.id]?.status ?? user.status}
                                    onChange={(event) => updateDraft(user.id, 'status', event.target.value as AdminUserStatus)}
                                />
                            </div>
                        ),
                    },
                    {
                        key: 'compliance',
                        header: 'Email trường',
                        render: (user: AdminUser) => (
                            <div className="space-y-2">
                                <Badge tone={getComplianceTone(user.isInternalDomainCompliant)}>
                                    {user.isInternalDomainCompliant ? 'Hợp lệ' : 'Cần rà soát'}
                                </Badge>
                                <div className="text-xs text-gray-500 dark:text-slate-400">Hoạt động cuối {formatDateTime(user.lastActiveAt)}</div>
                            </div>
                        ),
                    },
                    {
                        key: 'actions',
                        header: 'Lưu',
                        render: (user: AdminUser) => (
                            <Button
                                variant={isDraftDirty(user, drafts[user.id]) ? 'primary' : 'secondary'}
                                disabled={!isDraftDirty(user, drafts[user.id])}
                                isLoading={adminUserPatchMutation.isPending}
                                onClick={() => void handleSave(user)}
                            >
                                Lưu
                            </Button>
                        ),
                    },
                ]}
            />
        </div>
    )
}
