import { Bot } from 'lucide-react'
import { ChatWorkspace } from '@/features/chat/ChatWorkspace'
import { useScenarioParam } from '@/shared/lib/scenario'
import { PageHeader } from '@/shared/ui'

export default function ChatPage() {
    const scenario = useScenarioParam()

    return (
        <div className="space-y-6">
            <PageHeader
                title="Assistant chat"
                description="Public-facing answer workspace with citations, warning contract, confidence cues and reference-aware thread switching."
                icon={Bot}
            />
            <ChatWorkspace scenario={scenario} />
        </div>
    )
}
