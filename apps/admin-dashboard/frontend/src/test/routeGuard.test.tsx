import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { RouteGuard } from '@/app/guards/RouteGuard'
import { createAppQueryClient } from '@/shared/lib/queryClient'

function renderGuard(initialEntry: string) {
    const queryClient = createAppQueryClient()

    return render(
        <QueryClientProvider client={queryClient}>
            <MemoryRouter initialEntries={[initialEntry]}>
                <Routes>
                    <Route path="/portal" element={<Outlet />}>
                        <Route element={<RouteGuard allowedRoles={['lecturer', 'operator', 'admin']} />}>
                            <Route path="upload" element={<div>Upload page</div>} />
                        </Route>
                    </Route>
                    <Route path="/403" element={<div>Forbidden page</div>} />
                </Routes>
            </MemoryRouter>
        </QueryClientProvider>,
    )
}

describe('RouteGuard', () => {
    it('shows session error state instead of redirecting to 403 when auth lookup fails', async () => {
        renderGuard('/portal/upload?scenario=auth-error')

        expect(await screen.findByText('Unable to validate session')).toBeInTheDocument()
        expect(screen.getByText('Unable to validate the current session.')).toBeInTheDocument()
        expect(screen.queryByText('Forbidden page')).not.toBeInTheDocument()
    })
})
