import { Users } from 'lucide-react'
import { AdminUsersPanel } from '@/features/admin/AdminUsersPanel'
import { useScenarioParam } from '@/shared/lib/scenario'
import { PageHeader } from '@/shared/ui'

export default function UsersPage() {
    const scenario = useScenarioParam()

    return (
        <div className="space-y-6">
            <PageHeader
                title="Users"
                description="Manage role assignments, shell scope and institutional domain compliance."
                icon={Users}
            />
            <AdminUsersPanel scenario={scenario} />
        </div>
    )
}
