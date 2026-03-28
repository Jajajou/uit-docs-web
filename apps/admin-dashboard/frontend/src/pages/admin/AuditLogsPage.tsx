import { ScrollText } from 'lucide-react'
import { AuditLogsPanel } from '@/features/admin/AuditLogsPanel'
import { useScenarioParam } from '@/shared/lib/scenario'
import { PageHeader } from '@/shared/ui'

export default function AuditLogsPage() {
    const scenario = useScenarioParam()

    return (
        <div className="space-y-6">
            <PageHeader
                title="Audit logs"
                description="Trace uploads, review decisions, document archival and session-level admin actions."
                icon={ScrollText}
            />
            <AuditLogsPanel scenario={scenario} />
        </div>
    )
}
