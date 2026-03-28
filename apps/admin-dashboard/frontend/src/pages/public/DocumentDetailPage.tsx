import { useParams } from 'react-router-dom'
import { FileSearch } from 'lucide-react'
import { DocumentDetailPanel } from '@/features/documents/DocumentDetailPanel'
import { useScenarioParam } from '@/shared/lib/scenario'
import { PageHeader } from '@/shared/ui'

export default function DocumentDetailPage() {
    const { id = '' } = useParams()
    const scenario = useScenarioParam()

    return (
        <div className="space-y-6">
            <PageHeader
                title="Document detail"
                description="Public-facing trust detail for citations, provenance, visibility and assistant usage readiness."
                icon={FileSearch}
            />
            <DocumentDetailPanel id={id} scenario={scenario} />
        </div>
    )
}
