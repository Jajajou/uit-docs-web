import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/shared/ui/primitives/Button'
import { Card } from '@/shared/ui/primitives/Card'

interface AppErrorBoundaryProps {
    children: ReactNode
}

interface AppErrorBoundaryState {
    hasError: boolean
}

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
    state: AppErrorBoundaryState = {
        hasError: false,
    }

    static getDerivedStateFromError() {
        return { hasError: true }
    }

    componentDidCatch(_error: Error, _info: ErrorInfo) {}

    render() {
        if (this.state.hasError) {
            return (
                <div className="flex min-h-screen items-center justify-center bg-gray-50 p-6 dark:bg-gray-950">
                    <Card className="max-w-lg space-y-4 text-center">
                        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-error-50 text-error-700 dark:bg-error-950 dark:text-error-300">
                            <AlertTriangle size={24} />
                        </div>
                        <div className="space-y-1">
                            <h1 className="text-xl font-bold text-gray-950 dark:text-white">Unexpected UI error</h1>
                            <p className="text-sm text-gray-500">Reload the page to restore the foundational shell.</p>
                        </div>
                        <Button onClick={() => window.location.reload()}>Reload application</Button>
                    </Card>
                </div>
            )
        }

        return this.props.children
    }
}
