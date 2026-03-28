import { Upload } from 'lucide-react'
import { UploadWorkspace } from '@/features/uploads/UploadWorkspace'
import { useScenarioParam } from '@/shared/lib/scenario'
import { PageHeader } from '@/shared/ui'

export default function UploadPage() {
    const scenario = useScenarioParam()

    return (
        <div className="space-y-6">
            <PageHeader
                title="Upload workspace"
                description="Lecturer-facing intake flow with source-specific validation, review checklist and temporal metadata preview."
                icon={Upload}
            />
            <UploadWorkspace scenario={scenario} />
        </div>
    )
}
