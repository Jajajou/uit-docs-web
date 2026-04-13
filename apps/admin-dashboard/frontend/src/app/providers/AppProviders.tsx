import { type ReactNode, useEffect } from 'react'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'
import { AppErrorBoundary } from '@/app/providers/AppErrorBoundary'
import { QueryProvider } from '@/app/providers/QueryProvider'
import { syncThemeToDocument, useThemeStore } from '@/entities/preferences/theme'

interface AppProvidersProps {
    children: ReactNode
}

export default function AppProviders({ children }: AppProvidersProps) {
    const theme = useThemeStore((state) => state.theme)

    useEffect(() => {
        syncThemeToDocument(theme)
    }, [theme])

    return (
        <AppErrorBoundary>
            <QueryProvider>
                <BrowserRouter>
                    <Toaster
                        position="top-right"
                        theme={theme}
                        toastOptions={{
                            style:
                                theme === 'dark'
                                    ? {
                                          background: '#0f172a',
                                          border: '1px solid #1e293b',
                                          color: '#ffffff',
                                      }
                                    : {
                                          background: '#ffffff',
                                          border: '1px solid #cbd5e1',
                                          color: '#0f172a',
                                      },
                        }}
                    />
                    {children}
                </BrowserRouter>
            </QueryProvider>
        </AppErrorBoundary>
    )
}
