import { type ReactNode } from 'react'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'
import { AppErrorBoundary } from '@/app/providers/AppErrorBoundary'
import { QueryProvider } from '@/app/providers/QueryProvider'

interface AppProvidersProps {
    children: ReactNode
}

export default function AppProviders({ children }: AppProvidersProps) {
    return (
        <AppErrorBoundary>
            <QueryProvider>
                <BrowserRouter>
                <Toaster
                    position="top-right"
                    theme="dark"
                    toastOptions={{
                        style: {
                            background: '#0f172a',
                            border: '1px solid #1e293b',
                            color: '#ffffff',
                        },
                    }}
                />
                {children}
                </BrowserRouter>
            </QueryProvider>
        </AppErrorBoundary>
    )
}
