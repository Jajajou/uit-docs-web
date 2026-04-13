import { useDeferredValue, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ScrollText } from 'lucide-react'
import { formatAuditAction, getAuditTargetPath } from '@/entities/admin/presentation'
import { useAuditLogsQuery } from '@/entities/admin/queries'
import type { AuditActionType, AuditLogEntry, AuditTargetType } from '@/entities/admin/types'
import type { Role } from '@/entities/auth/types'
import { formatDateTime } from '@/shared/lib/format'
import { Badge, Card, FilterBar, Select } from '@/shared/ui'
import { DataTable } from '@/shared/ui/composites/DataTable'

type RoleFilter = 'all' | Role
type ActionFilter = 'all' | AuditActionType
type TargetTypeFilter = 'all' | AuditTargetType

const roleOptions = [
    { label: 'All actors', value: 'all' },
    { label: 'Student', value: 'student' },
    { label: 'Teacher', value: 'teacher' },
    { label: 'Admin', value: 'admin' },
]

const actionOptions = [
    { label: 'All actions', value: 'all' },
    { label: 'Upload submission', value: 'upload_submission' },
    { label: 'Approve review', value: 'approve_review' },
    { label: 'Reject review', value: 'reject_review' },
    { label: 'Request changes', value: 'request_changes' },
    { label: 'Archive document', value: 'archive_document' },
    { label: 'Reindex document', value: 'reindex_document' },
    { label: 'Login', value: 'login' },
    { label: 'Role switch', value: 'role_switch' },
]

const targetTypeOptions = [
    { label: 'All targets', value: 'all' },
    { label: 'Submission', value: 'submission' },
    { label: 'Review', value: 'review' },
    { label: 'Document', value: 'document' },
    { label: 'Session', value: 'session' },
]

function getActionTone(action: AuditActionType) {
    switch (action) {
        case 'approve_review':
            return 'success' as const
        case 'request_changes':
            return 'warning' as const
        case 'reject_review':
        case 'archive_document':
            return 'danger' as const
        case 'reindex_document':
            return 'brand' as const
        case 'role_switch':
            return 'warning' as const
        default:
            return 'brand' as const
    }
}

export function AuditLogsPanel({ scenario }: { scenario?: string }) {
    const auditLogsQuery = useAuditLogsQuery({ scenario })
    const [searchParams] = useSearchParams()
    const [searchValue, setSearchValue] = useState(() => searchParams.get('search') ?? '')
    const [roleFilter, setRoleFilter] = useState<RoleFilter>(() => (searchParams.get('actorRole') as RoleFilter) ?? 'all')
    const [actionFilter, setActionFilter] = useState<ActionFilter>(() => (searchParams.get('action') as ActionFilter) ?? 'all')
    const [targetTypeFilter, setTargetTypeFilter] = useState<TargetTypeFilter>(
        () => (searchParams.get('targetType') as TargetTypeFilter) ?? 'all',
    )
    const deferredSearch = useDeferredValue(searchValue)

    const filteredLogs = useMemo(() => {
        const normalizedSearch = deferredSearch.trim().toLowerCase()

        return (auditLogsQuery.data ?? []).filter((entry) => {
            const matchesSearch =
                normalizedSearch.length === 0 ||
                entry.actorName.toLowerCase().includes(normalizedSearch) ||
                entry.targetLabel.toLowerCase().includes(normalizedSearch) ||
                entry.targetId.toLowerCase().includes(normalizedSearch) ||
                formatAuditAction(entry.action).toLowerCase().includes(normalizedSearch)

            const matchesRole = roleFilter === 'all' || entry.actorRole === roleFilter
            const matchesAction = actionFilter === 'all' || entry.action === actionFilter
            const matchesTargetType = targetTypeFilter === 'all' || entry.targetType === targetTypeFilter

            return matchesSearch && matchesRole && matchesAction && matchesTargetType
        })
    }, [actionFilter, auditLogsQuery.data, deferredSearch, roleFilter, targetTypeFilter])

    const logs = auditLogsQuery.data ?? []

    if (auditLogsQuery.isError) {
        return <Card className="text-sm text-error-700 dark:text-error-300">{auditLogsQuery.error.message}</Card>
    }

    return (
        <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Visible audit events</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">{logs.length}</div>
                </Card>
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Review decisions</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">
                        {logs.filter((entry) => entry.targetType === 'review').length}
                    </div>
                </Card>
                <Card className="space-y-1">
                    <div className="text-sm font-medium text-gray-500">Document actions</div>
                    <div className="text-2xl font-semibold text-gray-950 dark:text-white">
                        {logs.filter((entry) => entry.targetType === 'document').length}
                    </div>
                </Card>
            </div>

            <FilterBar
                searchValue={searchValue}
                onSearchChange={setSearchValue}
                searchPlaceholder="Search by actor, action or target..."
                actions={
                    <>
                        <div className="min-w-48">
                            <Select
                                aria-label="Filter audit logs by actor role"
                                options={roleOptions}
                                value={roleFilter}
                                onChange={(event) => setRoleFilter(event.target.value as RoleFilter)}
                            />
                        </div>
                        <div className="min-w-52">
                            <Select
                                aria-label="Filter audit logs by action"
                                options={actionOptions}
                                value={actionFilter}
                                onChange={(event) => setActionFilter(event.target.value as ActionFilter)}
                            />
                        </div>
                        <div className="min-w-48">
                            <Select
                                aria-label="Filter audit logs by target type"
                                options={targetTypeOptions}
                                value={targetTypeFilter}
                                onChange={(event) => setTargetTypeFilter(event.target.value as TargetTypeFilter)}
                            />
                        </div>
                    </>
                }
            />

            <DataTable
                rows={filteredLogs}
                getRowKey={(entry) => entry.id}
                isLoading={auditLogsQuery.isLoading}
                emptyIcon={ScrollText}
                emptyTitle="No audit logs to show"
                emptyDescription="Try a broader search or reset the audit filters."
                columns={[
                    {
                        key: 'when',
                        header: 'When',
                        render: (entry: AuditLogEntry) => formatDateTime(entry.createdAt),
                    },
                    {
                        key: 'actor',
                        header: 'Actor',
                        render: (entry: AuditLogEntry) => (
                            <div className="space-y-1">
                                <div className="font-medium text-gray-900 dark:text-white">{entry.actorName}</div>
                                <div className="text-xs text-gray-500">{entry.actorRole}</div>
                            </div>
                        ),
                    },
                    {
                        key: 'action',
                        header: 'Action',
                        render: (entry: AuditLogEntry) => (
                            <Badge tone={getActionTone(entry.action)}>{formatAuditAction(entry.action)}</Badge>
                        ),
                    },
                    {
                        key: 'target',
                        header: 'Target',
                        render: (entry: AuditLogEntry) => {
                            const targetPath = getAuditTargetPath(entry)

                            return targetPath ? (
                                <Link to={targetPath} className="font-medium text-gray-900 hover:text-brand-700 dark:text-white">
                                    {entry.targetLabel}
                                </Link>
                            ) : (
                                <span className="text-gray-700 dark:text-gray-200">{entry.targetLabel}</span>
                            )
                        },
                    },
                    {
                        key: 'type',
                        header: 'Target type',
                        render: (entry: AuditLogEntry) => entry.targetType,
                    },
                ]}
            />
        </div>
    )
}
