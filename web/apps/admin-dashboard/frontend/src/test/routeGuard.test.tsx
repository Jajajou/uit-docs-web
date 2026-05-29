import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError } from '@/shared/api/error'
import type { Session } from '@/entities/auth/types'

const { useSessionQueryMock, useScenarioParamMock } = vi.hoisted(() => ({
    useSessionQueryMock: vi.fn(),
    useScenarioParamMock: vi.fn(),
}))

vi.mock('@/entities/auth/queries', () => ({
    useSessionQuery: useSessionQueryMock,
}))

vi.mock('@/shared/lib/scenario', () => ({
    useScenarioParam: useScenarioParamMock,
}))

import { RouteGuard } from '@/app/guards/RouteGuard'

function buildSession(overrides: Partial<Session> = {}): Session {
    return {
        id: 'session-001',
        status: 'authenticated',
        user: {
            id: 'user-001',
            name: 'Nguyen Van Teacher',
            email: 'teacher@gm.uit.edu.vn',
            role: 'teacher',
            department: 'Giang vien UIT',
            avatarInitials: 'NT',
        },
        ...overrides,
    }
}

function renderGuard(initialEntry = '/upload') {
    return render(
        <MemoryRouter initialEntries={[initialEntry]}>
            <Routes>
                <Route path="/upload" element={<RouteGuard allowedRoles={['teacher', 'admin']} />}>
                    <Route index element={<div>Protected upload page</div>} />
                </Route>
                <Route path="/403" element={<div>Forbidden page</div>} />
            </Routes>
        </MemoryRouter>,
    )
}

describe('RouteGuard', () => {
    beforeEach(() => {
        useScenarioParamMock.mockReturnValue('happy')
        useSessionQueryMock.mockReset()
    })

    it('shows a skeleton state while the session check is loading', () => {
        useSessionQueryMock.mockReturnValue({
            data: undefined,
            error: null,
            isLoading: true,
            isError: false,
            refetch: vi.fn(),
        })

        const { container } = renderGuard()

        expect(container.querySelectorAll('.animate-pulse')).toHaveLength(2)
        expect(screen.queryByText('Forbidden page')).not.toBeInTheDocument()
    })

    it('shows a retryable error card when session validation fails', () => {
        const refetch = vi.fn()
        useSessionQueryMock.mockReturnValue({
            data: undefined,
            error: new ApiClientError({
                code: 'auth_fetch_failed',
                message: 'Unable to validate the current session.',
                status: 500,
                requestId: 'req-guard-001',
            }),
            isLoading: false,
            isError: true,
            refetch,
        })

        renderGuard()

        expect(screen.getByText('Unable to validate session')).toBeInTheDocument()
        expect(screen.getByText('Unable to validate the current session.')).toBeInTheDocument()
        expect(screen.getByText('Request ID: req-guard-001')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: 'Retry session check' }))
        expect(refetch).toHaveBeenCalledTimes(1)
        expect(screen.getByRole('link', { name: 'Switch role' })).toHaveAttribute('href', '/auth/login')
    })

    it('redirects to 403 when the role is not allowed for the route', async () => {
        useSessionQueryMock.mockReturnValue({
            data: buildSession({
                user: {
                    id: 'user-002',
                    name: 'Student User',
                    email: 'student@gm.uit.edu.vn',
                    role: 'student',
                    department: 'Sinh vien UIT',
                    avatarInitials: 'SU',
                },
            }),
            error: null,
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })

        renderGuard()

        expect(await screen.findByText('Forbidden page')).toBeInTheDocument()
        expect(screen.queryByText('Protected upload page')).not.toBeInTheDocument()
    })

    it('redirects to 403 when an internal role does not satisfy the UIT email rule', async () => {
        useSessionQueryMock.mockReturnValue({
            data: buildSession({
                user: {
                    id: 'user-003',
                    name: 'Teacher External',
                    email: 'teacher@gmail.com',
                    role: 'teacher',
                    department: 'Giang vien UIT',
                    avatarInitials: 'TE',
                },
            }),
            error: null,
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })

        renderGuard()

        expect(await screen.findByText('Forbidden page')).toBeInTheDocument()
    })

    it('renders the protected outlet when the session is valid', async () => {
        useSessionQueryMock.mockReturnValue({
            data: buildSession(),
            error: null,
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })

        renderGuard()

        expect(await screen.findByText('Protected upload page')).toBeInTheDocument()
        expect(screen.queryByText('Forbidden page')).not.toBeInTheDocument()
    })
})
