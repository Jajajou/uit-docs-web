import { ShieldCheck } from 'lucide-react'
import { routeMeta } from '@/app/config/routes'
import { getPolicyShellSummary } from '@/entities/admin/presentation'
import { useRolePoliciesQuery } from '@/entities/admin/queries'
import type { RolePolicy } from '@/entities/admin/types'
import { Badge, Card } from '@/shared/ui'
import { DataTable } from '@/shared/ui/composites/DataTable'

function getRoleTone(role: RolePolicy['role']) {
    switch (role) {
        case 'admin':
            return 'danger' as const
        case 'operator':
            return 'brand' as const
        case 'lecturer':
            return 'success' as const
        case 'student':
            return 'neutral' as const
        default:
            return 'warning' as const
    }
}

export function RolePoliciesPanel({ scenario }: { scenario?: string }) {
    const rolePoliciesQuery = useRolePoliciesQuery({ scenario })

    if (rolePoliciesQuery.isError) {
        return <Card className="text-sm text-error-700 dark:text-error-300">{rolePoliciesQuery.error.message}</Card>
    }

    return (
        <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
                <Card className="space-y-2">
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">Route contract summary</div>
                    <p className="text-sm text-gray-500">
                        The matrix below is derived from the live route contract and the backend role policy endpoint. It reflects the same guard logic used by the app runtime.
                    </p>
                    <div className="flex flex-wrap gap-2">
                        <Badge tone="neutral">{routeMeta.length} routes</Badge>
                        <Badge tone="brand">{routeMeta.filter((route) => route.shell === 'portal').length} portal</Badge>
                        <Badge tone="danger">{routeMeta.filter((route) => route.shell === 'admin').length} admin</Badge>
                    </div>
                </Card>
                <Card className="space-y-2 border-brand-200 bg-brand-50 dark:border-brand-900 dark:bg-brand-950">
                    <div className="text-sm font-semibold text-brand-800 dark:text-brand-200">Policy summary</div>
                    <p className="text-sm text-brand-700 dark:text-brand-300">
                        Internal roles require institutional email and are blocked at the route guard if the session email is non-compliant. Uploads must pass operator review before publication, and public chat must always expose citations and warnings.
                    </p>
                    <p className="text-sm text-brand-700 dark:text-brand-300">
                        Admin retains a narrow break-glass support override for operator-owned remediation flows such as review decisions, job retry, archive and reindex. Those actions should be labeled explicitly and remain visible in audit logs.
                    </p>
                </Card>
            </div>

            <DataTable
                rows={rolePoliciesQuery.data ?? []}
                getRowKey={(policy) => policy.role}
                isLoading={rolePoliciesQuery.isLoading}
                emptyIcon={ShieldCheck}
                emptyTitle="No role policies found"
                emptyDescription="Role policy data is empty for this scenario."
                columns={[
                    {
                        key: 'role',
                        header: 'Role',
                        render: (policy) => <Badge tone={getRoleTone(policy.role)}>{policy.role}</Badge>,
                    },
                    {
                        key: 'shells',
                        header: 'Allowed shells',
                        render: (policy) => getPolicyShellSummary(policy),
                    },
                    {
                        key: 'domain',
                        header: 'Internal email',
                        render: (policy) => (
                            <Badge tone={policy.requiresInternalEmail ? 'warning' : 'neutral'}>
                                {policy.requiresInternalEmail ? 'Required' : 'Not required'}
                            </Badge>
                        ),
                    },
                    {
                        key: 'routes',
                        header: 'Allowed routes',
                        render: (policy) => (
                            <div className="flex flex-wrap gap-2">
                                {policy.allowedRoutes.map((route) => (
                                    <Badge key={`${policy.role}-${route}`} tone="neutral">
                                        {route}
                                    </Badge>
                                ))}
                            </div>
                        ),
                    },
                ]}
            />
        </div>
    )
}
