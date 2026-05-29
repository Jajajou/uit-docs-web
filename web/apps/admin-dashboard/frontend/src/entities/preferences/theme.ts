import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ThemeMode = 'light' | 'dark'

interface ThemeState {
    theme: ThemeMode
    setTheme: (theme: ThemeMode) => void
    toggleTheme: () => void
}

export function syncThemeToDocument(theme: ThemeMode) {
    if (typeof document === 'undefined') {
        return
    }

    document.documentElement.classList.toggle('dark', theme === 'dark')
    document.documentElement.style.colorScheme = theme
}

export const useThemeStore = create<ThemeState>()(
    persist(
        (set) => ({
            theme: 'light',
            setTheme: (theme) => set({ theme }),
            toggleTheme: () =>
                set((state) => ({
                    theme: state.theme === 'dark' ? 'light' : 'dark',
                })),
        }),
        {
            name: 'uit-docs-agent-theme',
        },
    ),
)
