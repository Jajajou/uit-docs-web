import { Settings } from 'lucide-react'
import { SettingsPanels } from '@/features/admin/SettingsPanels'
import { useScenarioParam } from '@/shared/lib/scenario'
import { PageHeader } from '@/shared/ui'

export default function SettingsPage() {
    const scenario = useScenarioParam()

    return (
        <div className="space-y-6">
            <PageHeader
                title="Settings"
                description="Adjust contract-backed policy surfaces for auth, ingestion, publication and chat citation behavior."
                icon={Settings}
            />
            <SettingsPanels scenario={scenario} />
        </div>
    )
}
