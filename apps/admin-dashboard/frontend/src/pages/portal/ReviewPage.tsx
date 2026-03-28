import { ClipboardList } from 'lucide-react'
import { ReviewQueue } from '@/features/review/ReviewQueue'
import { useScenarioParam } from '@/shared/lib/scenario'
import { PageHeader } from '@/shared/ui'

export default function ReviewPage() {
    const scenario = useScenarioParam()

    return (
        <div className="space-y-6">
            <PageHeader
                title="Review queue"
                description="Operator-facing decision workspace for validating extraction output and promoting approved submissions into public documents."
                icon={ClipboardList}
            />
            <ReviewQueue scenario={scenario} />
        </div>
    )
}
