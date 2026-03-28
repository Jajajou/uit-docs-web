import { Link } from 'react-router-dom'
import { SearchX } from 'lucide-react'
import { Button, Card, PageHeader } from '@/shared/ui'

export default function NotFoundPage() {
    return (
        <div className="space-y-6">
            <PageHeader title="Page not found" description="The requested route is not part of the foundational route contract." icon={SearchX} />
            <Card className="space-y-4">
                <p className="text-sm text-gray-600 dark:text-gray-300">Use one of the stable public, portal or admin namespaces instead.</p>
                <Button asChild>
                    <Link to="/">Back to home</Link>
                </Button>
            </Card>
        </div>
    )
}
