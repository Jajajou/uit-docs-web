import { useLocation, Link } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import { Button, Card, PageHeader } from '@/shared/ui'

export default function ForbiddenPage() {
    const location = useLocation()

    return (
        <div className="space-y-6">
            <PageHeader
                title="Access denied"
                description="This route is blocked by the current session role."
                icon={ShieldAlert}
            />
            <Card className="space-y-4">
                <p className="text-sm text-gray-600 dark:text-gray-300">
                    Attempted route: {String((location.state as { from?: string } | null)?.from ?? 'unknown')}
                </p>
                <div className="flex gap-3">
                    <Button asChild>
                        <Link to="/auth/login">Switch role</Link>
                    </Button>
                    <Button asChild variant="secondary">
                        <Link to="/">Return home</Link>
                    </Button>
                </div>
            </Card>
        </div>
    )
}
