import { Link } from 'react-router-dom'
import { Bot, FileSearch, Upload } from 'lucide-react'
import { Button, Card, PageHeader } from '@/shared/ui'

export default function HomePage() {
    return (
        <div className="space-y-8">
            <PageHeader
                title="UIT Knowledge Portal"
                description="Foundational public shell for student-facing search, citations and document-aware answers."
                icon={Bot}
                actions={
                    <>
                        <Button asChild>
                            <Link to="/chat">Open chat</Link>
                        </Button>
                        <Button asChild variant="secondary">
                            <Link to="/auth/login">Switch role</Link>
                        </Button>
                    </>
                }
            />

            <div className="grid gap-6 lg:grid-cols-3">
                <Card className="space-y-3">
                    <Bot className="text-brand-600" />
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">Public chat</div>
                    <p className="text-sm text-gray-500">Validate references, warnings and confidence states before backend streaming lands.</p>
                </Card>
                <Card className="space-y-3">
                    <FileSearch className="text-brand-600" />
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">Document detail</div>
                    <p className="text-sm text-gray-500">Public document route exposes temporal, system and supplemental metadata in a stable contract.</p>
                </Card>
                <Card className="space-y-3">
                    <Upload className="text-brand-600" />
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">Internal portal</div>
                    <p className="text-sm text-gray-500">Lecturers, operators and admins are separated by route guards and session role state.</p>
                </Card>
            </div>
        </div>
    )
}
