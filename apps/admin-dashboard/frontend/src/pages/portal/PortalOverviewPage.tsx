import { Link } from 'react-router-dom'
import { LayoutDashboard } from 'lucide-react'
import { Button, Card, PageHeader } from '@/shared/ui'

export default function PortalOverviewPage() {
    return (
        <div className="space-y-6">
            <PageHeader
                title="Portal overview"
                description="Internal shell entry point for contributor and operator workflows."
                icon={LayoutDashboard}
            />
            <div className="grid gap-6 lg:grid-cols-3">
                <Card className="space-y-4">
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">Upload foundation</div>
                    <p className="text-sm text-gray-500">Schema-aware upload flow with core metadata, extraction diagnostics and supplemental metadata slots.</p>
                    <Button asChild variant="secondary">
                        <Link to="/portal/upload">Open upload</Link>
                    </Button>
                </Card>
                <Card className="space-y-4">
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">Submission tracking</div>
                    <p className="text-sm text-gray-500">Contributor-safe list of pending, approved and rejected submissions.</p>
                    <Button asChild variant="secondary">
                        <Link to="/portal/submissions">View submissions</Link>
                    </Button>
                </Card>
                <Card className="space-y-4">
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">Operator queue</div>
                    <p className="text-sm text-gray-500">Review queue, library and job monitor remain isolated behind role guard.</p>
                    <Button asChild variant="secondary">
                        <Link to="/portal/review">Open review queue</Link>
                    </Button>
                </Card>
            </div>
        </div>
    )
}
