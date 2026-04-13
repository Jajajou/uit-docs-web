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
                title="Chi tiết tài liệu"
                description="Thông tin tóm tắt của tài liệu được dùng làm nguồn tham chiếu trong UIT AI."
                icon={FileSearch}
            />
            <DocumentDetailPanel id={id} scenario={scenario} />
        </div>
    )
}
