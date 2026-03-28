import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { SessionBootstrapRequest } from '@/entities/auth/bootstrap'
import type { Role } from '@/entities/auth/types'

interface SessionState {
    selectedRole: Role
    bootstrapRequest: SessionBootstrapRequest | null
    setRole: (role: Role) => void
    beginBootstrap: (role: Role, returnTo?: string | null) => void
    clearBootstrap: () => void
}

export const useSessionStore = create<SessionState>()(
    persist(
        (set) => ({
            selectedRole: 'guest',
            bootstrapRequest: null,
            setRole: (role) => set({ selectedRole: role }),
            beginBootstrap: (role, returnTo = null) =>
                set({
                    bootstrapRequest: {
                        role,
                        returnTo,
                        initiatedAt: new Date().toISOString(),
                    },
                }),
            clearBootstrap: () => set({ bootstrapRequest: null }),
        }),
        {
            name: 'uit-docs-agent-session',
        },
    ),
)
