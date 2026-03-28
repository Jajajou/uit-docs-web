import { type ReactNode, useState } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { createAppQueryClient } from '@/shared/lib/queryClient'

export function QueryProvider({ children }: { children: ReactNode }) {
    const [queryClient] = useState(() => createAppQueryClient())

    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}
