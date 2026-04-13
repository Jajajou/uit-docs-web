import { useLocation, useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import campusImage from '@/assets/auth/uit-campus-login.jpg'
import { buildAuthCallbackTarget, buildInternalSsoStartTarget } from '@/entities/auth/bootstrap'
import { useSsoProviderMetadataQuery } from '@/entities/auth/queries'
import { useSessionStore } from '@/entities/auth/store'
import type { Role } from '@/entities/auth/types'
import { isMockAdapterEnabled } from '@/shared/api/mockRuntime'
import { Button, Card } from '@/shared/ui'

function GoogleGlyph() {
    return (
        <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5 shrink-0">
            <path
                fill="#4285F4"
                d="M21.6 12.23c0-.72-.06-1.25-.19-1.8H12v3.4h5.52c-.11.85-.69 2.13-1.97 2.99l-.02.11 2.83 2.19.2.02c1.84-1.69 3.04-4.18 3.04-6.91Z"
            />
            <path
                fill="#34A853"
                d="M12 22c2.7 0 4.96-.89 6.61-2.42l-3.01-2.33c-.81.57-1.89.97-3.6.97-2.64 0-4.88-1.69-5.67-4.04l-.1.01-2.94 2.28-.03.1C4.9 19.86 8.16 22 12 22Z"
            />
            <path
                fill="#FBBC05"
                d="M6.33 14.18A5.96 5.96 0 0 1 6 12c0-.75.12-1.48.32-2.18l-.01-.14-2.98-2.31-.1.05A9.95 9.95 0 0 0 2 12c0 1.6.38 3.12 1.22 4.43l3.11-2.25Z"
            />
            <path
                fill="#EA4335"
                d="M12 5.78c2.14 0 3.58.92 4.4 1.69l3.22-3.14C17.95 2.73 14.7 2 12 2 8.16 2 4.9 4.14 3.22 7.57l3.09 2.4c.8-2.35 3.04-4.19 5.69-4.19Z"
            />
        </svg>
    )
}

export default function LoginPage() {
    const location = useLocation()
    const navigate = useNavigate()
    const queryClient = useQueryClient()
    const beginBootstrap = useSessionStore((state) => state.beginBootstrap)
    const requestedReturnTo = new URLSearchParams(location.search).get('returnTo')
    const ssoMetadataQuery = useSsoProviderMetadataQuery({ enabled: !isMockAdapterEnabled })
    const providerMetadata = ssoMetadataQuery.data

    const continueWithRole = (role: Role) => {
        beginBootstrap(role, requestedReturnTo)
        queryClient.removeQueries({ queryKey: ['auth', 'session'] })
        navigate(buildAuthCallbackTarget(role, requestedReturnTo))
    }

    const canStartGoogleFlow = isMockAdapterEnabled || (providerMetadata ? providerMetadata.configured : false)

    return (
        <Card className="animate-fade-in overflow-hidden rounded-[1.55rem] border border-white/90 bg-white/95 p-3 shadow-theme-lg dark:border-[#214263] dark:bg-[#091423]/92 sm:p-3.5">
            <div className="space-y-4">
                <div className="overflow-hidden rounded-[1rem] border border-brand-100 bg-brand-50 shadow-theme-sm dark:border-[#1d3755] dark:bg-[#0d1b2c]">
                    <div className="relative aspect-[16/10]">
                        <img src={campusImage} alt="Toàn cảnh khuôn viên UIT" className="h-full w-full object-cover" />
                        <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.04),rgba(8,18,34,0.08))] dark:bg-[linear-gradient(180deg,rgba(9,19,33,0.02),rgba(4,10,20,0.16))]" />
                    </div>
                </div>

                <div className="space-y-3 px-1 pb-1">
                    <p className="text-base leading-7 text-gray-600 dark:text-gray-200">
                        Chỉ chấp nhận tài khoản Google chính thức được cấp bởi trường UIT.
                    </p>

                    <Button
                        fullWidth
                        size="lg"
                        variant="secondary"
                        disabled={!canStartGoogleFlow}
                        className="h-12 rounded-[0.95rem] border border-gray-200 bg-white text-base text-gray-900 shadow-none hover:border-brand-300 hover:bg-white dark:border-[#3a5779] dark:bg-white dark:text-gray-900 dark:hover:border-brand-400 dark:hover:bg-white"
                        onClick={() => {
                            if (isMockAdapterEnabled) {
                                continueWithRole('student')
                                return
                            }

                            window.location.assign(buildInternalSsoStartTarget(requestedReturnTo))
                        }}
                    >
                        <GoogleGlyph />
                        Tiếp tục với Google
                        <ArrowRight size={18} />
                    </Button>

                    {!canStartGoogleFlow && !isMockAdapterEnabled ? (
                        <div className="rounded-[0.95rem] border border-warning-200 bg-warning-50 px-4 py-3 text-sm leading-6 text-warning-800 dark:border-warning-900 dark:bg-warning-950/40 dark:text-warning-300">
                            Backend chưa có <span className="font-semibold">SSO_CLIENT_ID</span> và <span className="font-semibold">SSO_CLIENT_SECRET</span>, nên nút Google đang bị khóa cho tới khi OAuth được cấu hình đầy đủ.
                        </div>
                    ) : null}
                </div>
            </div>
        </Card>
    )
}
