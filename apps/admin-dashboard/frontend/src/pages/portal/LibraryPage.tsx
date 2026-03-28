import { Library } from 'lucide-react'
import { DocumentLibrary } from '@/features/documents/DocumentLibrary'
import { useScenarioParam } from '@/shared/lib/scenario'
import { PageHeader } from '@/shared/ui'

export default function LibraryPage() {
    const scenario = useScenarioParam()

    return (
        <div className="space-y-6">
            <PageHeader
                title="Knowledge library"
                description="Contract-stable document table for operator and admin review."
                icon={Library}
            />
            <DocumentLibrary scenario={scenario} />
        </div>
    )
}
