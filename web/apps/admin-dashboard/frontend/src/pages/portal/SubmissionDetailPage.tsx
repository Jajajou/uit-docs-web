import { useParams } from 'react-router-dom'
import { FileStack } from 'lucide-react'
import { SubmissionDetailPanel } from '@/features/submissions/SubmissionDetailPanel'
import { useScenarioParam } from '@/shared/lib/scenario'
import { PageHeader } from '@/shared/ui'

export default function SubmissionDetailPage() {
    const { id = '' } = useParams()
    const scenario = useScenarioParam()

    return (
        <div className="space-y-6">
            <PageHeader
                title="Submission detail"
            description="Bridge teacher upload context with reviewer handoff, extraction diagnostics and publication readiness."
                icon={FileStack}
            />
            <SubmissionDetailPanel id={id} scenario={scenario} />
        </div>
    )
}
