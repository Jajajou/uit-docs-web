import { Library } from 'lucide-react'
import { DocumentLibrary } from '@/features/documents/DocumentLibrary'
import { useScenarioParam } from '@/shared/lib/scenario'
import { PageHeader } from '@/shared/ui'

export default function LibraryPage() {
    const scenario = useScenarioParam()

    return (
        <div className="space-y-6">
            <PageHeader
                title="Thư viện tài liệu"
                description="Danh sách tài liệu đã được hệ thống ghi nhận để tra cứu và rà soát."
                icon={Library}
            />
            <DocumentLibrary scenario={scenario} />
        </div>
    )
}
