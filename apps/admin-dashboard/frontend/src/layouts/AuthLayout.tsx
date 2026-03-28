import { Outlet } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'

export default function AuthLayout() {
    return (
        <div className="min-h-screen bg-gray-50 px-4 py-10 dark:bg-gray-950">
            <div className="mx-auto flex max-w-5xl items-center justify-center gap-10 lg:min-h-[calc(100vh-5rem)]">
                <div className="hidden max-w-md space-y-4 lg:block">
                    <div className="inline-flex items-center gap-2 rounded-full bg-brand-50 px-3 py-1 text-sm font-semibold text-brand-700 dark:bg-brand-950 dark:text-brand-200">
                        <ShieldCheck size={16} />
                        Foundation auth shell
                    </div>
                    <h1 className="text-4xl font-bold tracking-tight text-gray-950 dark:text-white">
                        Stable auth namespace before real UIT SSO
                    </h1>
                    <p className="text-base text-gray-500">
                        This shell exists now so route contracts, role switching and callback handling stay stable when backend auth is introduced.
                    </p>
                </div>

                <div className="w-full max-w-xl rounded-3xl border border-gray-200 bg-white p-6 shadow-theme-xl dark:border-gray-800 dark:bg-gray-900 sm:p-8">
                    <Outlet />
                </div>
            </div>
        </div>
    )
}
