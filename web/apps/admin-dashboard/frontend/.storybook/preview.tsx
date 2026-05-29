import type { Preview } from '@storybook/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { createAppQueryClient } from '../src/shared/lib/queryClient'
import '../src/app/styles/index.css'

const preview: Preview = {
    decorators: [
        (Story) => {
            const queryClient = createAppQueryClient()

            return (
                <MemoryRouter>
                    <QueryClientProvider client={queryClient}>
                        <Toaster />
                        <div className="min-h-screen bg-gray-50 p-6 dark:bg-gray-950">
                            <Story />
                        </div>
                    </QueryClientProvider>
                </MemoryRouter>
            )
        },
    ],
    parameters: {
        layout: 'fullscreen',
    },
}

export default preview
