import { Workflow } from 'lucide-react'
import { JobsTable } from '@/features/jobs/JobsTable'
import { useScenarioParam } from '@/shared/lib/scenario'
import { PageHeader } from '@/shared/ui'

export default function JobsPage() {
    const scenario = useScenarioParam()

    return (
        <div className="space-y-6">
            <PageHeader
                title="Jobs monitor"
                description="Pipeline monitoring shell for upload, indexing and scan jobs."
                icon={Workflow}
            />
            <JobsTable scenario={scenario} />
        </div>
    )
}
