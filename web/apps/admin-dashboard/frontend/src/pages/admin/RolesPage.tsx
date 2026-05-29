import { ShieldCheck } from 'lucide-react'
import { RolePoliciesPanel } from '@/features/admin/RolePoliciesPanel'
import { useScenarioParam } from '@/shared/lib/scenario'
import { PageHeader } from '@/shared/ui'

export default function RolesPage() {
    const scenario = useScenarioParam()

    return (
        <div className="space-y-6">
            <PageHeader
                title="Roles"
                description="Route-to-role matrix and policy summary derived from the current frontend RBAC contract."
                icon={ShieldCheck}
            />
            <RolePoliciesPanel scenario={scenario} />
        </div>
    )
}
