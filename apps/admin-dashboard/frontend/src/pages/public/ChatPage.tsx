import { ChatWorkspace } from '@/features/chat/ChatWorkspace'
import { useScenarioParam } from '@/shared/lib/scenario'

export default function ChatPage() {
    const scenario = useScenarioParam()

    return (
        <div className="h-full w-full overflow-hidden">
            <ChatWorkspace scenario={scenario} />
        </div>
    )
}
