import { Files } from 'lucide-react'
import { SubmissionsTable } from '@/features/submissions/SubmissionsTable'
import { useScenarioParam } from '@/shared/lib/scenario'
import { PageHeader } from '@/shared/ui'

export default function SubmissionsPage() {
    const scenario = useScenarioParam()

    return (
        <div className="space-y-6">
            <PageHeader
                title="Submissions"
                description="Contributor-facing list of uploads and approval state."
                icon={Files}
            />
            <SubmissionsTable scenario={scenario} />
        </div>
    )
}
