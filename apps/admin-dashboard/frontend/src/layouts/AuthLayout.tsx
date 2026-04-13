import { Outlet } from 'react-router-dom'
import { Moon, Sun } from 'lucide-react'
import { useThemeStore } from '@/entities/preferences/theme'
import { Button } from '@/shared/ui'

export default function AuthLayout() {
    const theme = useThemeStore((state) => state.theme)
    const toggleTheme = useThemeStore((state) => state.toggleTheme)

    return (
        <div className="surface-grid relative min-h-screen overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(47,86,245,0.1),transparent_22%),linear-gradient(180deg,rgba(255,255,255,0.56),rgba(248,251,255,0.84))] dark:bg-[radial-gradient(circle_at_top_left,rgba(74,163,255,0.14),transparent_24%),radial-gradient(circle_at_bottom_right,rgba(47,86,245,0.14),transparent_28%),linear-gradient(180deg,rgba(4,10,20,0.28),rgba(4,10,20,0.54))]" />

            <div className="relative mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-6 sm:px-6">
                <div className="flex justify-end">
                    <Button variant="secondary" size="sm" onClick={toggleTheme} aria-label="Đổi giao diện sáng tối">
                        {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
                        {theme === 'dark' ? 'Sáng' : 'Tối'}
                    </Button>
                </div>

                <div className="flex flex-1 items-center justify-center py-6 sm:py-10">
                    <div className="w-full max-w-[28rem]">
                        <Outlet />
                    </div>
                </div>
            </div>
        </div>
    )
}
