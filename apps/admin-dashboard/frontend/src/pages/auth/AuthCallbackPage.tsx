import { useEffect, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowRight, Chrome, ShieldCheck } from 'lucide-react'
import { INTERNAL_EMAIL_DOMAIN } from '@/app/config/routes'
import {
    buildAuthCallbackTarget,
    buildInternalSsoStartTarget,
    readAuthError,
    readAuthErrorMessage,
    readBootstrapReturnTo,
    readBootstrapRole,
    resolveSessionRedirectPath,
} from '@/entities/auth/bootstrap'
import { useBootstrapSessionMutation, useSessionQuery } from '@/entities/auth/queries'
import { useSessionStore } from '@/entities/auth/store'
import { useScenarioParam } from '@/shared/lib/scenario'
import { Badge, Button, Card } from '@/shared/ui'

export default function AuthCallbackPage() {
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()
    const scenario = useScenarioParam()
    const selectedRole = useSessionStore((state) => state.selectedRole)
    const bootstrapRequest = useSessionStore((state) => state.bootstrapRequest)
    const clearBootstrap = useSessionStore((state) => state.clearBootstrap)
    const setRole = useSessionStore((state) => state.setRole)

    const hasExplicitBootstrap = searchParams.get('bootstrap') === '1' || bootstrapRequest !== null
    const requestedRole = readBootstrapRole(searchParams) ?? bootstrapRequest?.role ?? null
    const requestedReturnTo = readBootstrapReturnTo(searchParams) ?? bootstrapRequest?.returnTo ?? null
    const authErrorCode = readAuthError(searchParams)
    const authErrorMessage = readAuthErrorMessage(searchParams)

    const {
        data: bootstrapSession,
        error: bootstrapError,
        isError: isBootstrapError,
        isPending: isBootstrapping,
        mutate: bootstrapRole,
        reset: resetBootstrapMutation,
        status: bootstrapStatus,
    } = useBootstrapSessionMutation({ scenario })

    const sessionQuery = useSessionQuery({ scenario, enabled: !hasExplicitBootstrap && !authErrorCode })
    const activeSession = bootstrapSession ?? sessionQuery.data
    const activeError = bootstrapError ?? sessionQuery.error

    const redirectTarget = useMemo(
        () => (activeSession ? resolveSessionRedirectPath(activeSession.user.role, requestedReturnTo) : null),
        [activeSession, requestedReturnTo],
    )

    useEffect(() => {
        if (hasExplicitBootstrap && requestedRole && bootstrapStatus === 'idle') {
            bootstrapRole(requestedRole)
        }
    }, [bootstrapRole, bootstrapStatus, hasExplicitBootstrap, requestedRole])

    useEffect(() => {
        if (activeSession && redirectTarget) {
            setRole(activeSession.user.role)
            clearBootstrap()
            navigate(redirectTarget, { replace: true })
        }
    }, [activeSession, clearBootstrap, navigate, redirectTarget, setRole])

    if (authErrorCode || isBootstrapError || sessionQuery.isError || (hasExplicitBootstrap && !requestedRole)) {
        const errorMessage =
            authErrorMessage
                ? authErrorMessage
                : hasExplicitBootstrap && !requestedRole
                  ? 'Thiếu role yêu cầu nên không thể hoàn tất đăng nhập.'
                  : activeError instanceof Error
                    ? activeError.message
                    : 'Không thể hoàn tất callback đăng nhập hiện tại.'
        const retrySso = !hasExplicitBootstrap && authErrorCode

        return (
            <div className="space-y-6">
                <div className="space-y-3">
                    <Badge tone="warning">Đăng nhập chưa hoàn tất</Badge>
                    <h2 className="text-3xl font-bold tracking-tight text-gray-950 dark:text-white">Không thể xác thực phiên làm việc</h2>
                    <p className="text-sm leading-7 text-gray-500">
                        Backend đã từ chối callback do lỗi provider, thiếu state hoặc email không thỏa điều kiện miền trường {INTERNAL_EMAIL_DOMAIN}.
                    </p>
                </div>

                <Card className="space-y-4">
                    <div className="flex flex-wrap gap-2">
                        {authErrorCode ? <Badge tone="warning">Mã lỗi {authErrorCode}</Badge> : null}
                        {requestedRole ? <Badge tone="neutral">Role yêu cầu {requestedRole}</Badge> : null}
                        {requestedReturnTo ? <Badge tone="neutral">Điểm đến {requestedReturnTo}</Badge> : null}
                    </div>

                    <div className="rounded-2xl border border-error-200 bg-error-50 px-4 py-4 text-sm leading-6 text-error-700 dark:border-error-900 dark:bg-error-950/50 dark:text-error-300">
                        {errorMessage}
                    </div>

                    <div className="flex flex-wrap gap-3">
                        {retrySso ? (
                            <Button
                                type="button"
                                onClick={() => {
                                    window.location.assign(buildInternalSsoStartTarget(requestedReturnTo))
                                }}
                            >
                                <Chrome size={16} />
                                Thử lại với Google
                            </Button>
                        ) : (
                            <Button
                                type="button"
                                onClick={() => {
                                    if (requestedRole && hasExplicitBootstrap) {
                                        navigate(buildAuthCallbackTarget(requestedRole, requestedReturnTo), { replace: true })
                                        resetBootstrapMutation()
                                        bootstrapRole(requestedRole)
                                        return
                                    }

                                    void sessionQuery.refetch()
                                }}
                            >
                                <ArrowRight size={16} />
                                {hasExplicitBootstrap ? 'Thử bootstrap lại' : 'Kiểm tra lại phiên'}
                            </Button>
                        )}

                        <Button type="button" variant="secondary" onClick={() => navigate('/auth/login', { replace: true })}>
                            Quay lại đăng nhập
                        </Button>
                    </div>
                </Card>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div className="space-y-3">
                <Badge tone="brand">Đang xác thực</Badge>
                <h2 className="text-3xl font-bold tracking-tight text-gray-950 dark:text-white">Đang hoàn tất phiên Google Workspace UIT</h2>
                <p className="text-sm leading-7 text-gray-500">
                    Hệ thống đang kiểm tra email trường, role được gán trong backend và điều hướng anh vào đúng khu làm việc.
                </p>
            </div>

            <Card className="space-y-5">
                <div className="flex flex-wrap gap-2">
                    {requestedRole ? <Badge tone="brand">Role yêu cầu {requestedRole}</Badge> : <Badge tone="brand">Role hiện tại {selectedRole}</Badge>}
                    {redirectTarget ? <Badge tone="success">Đi tới {redirectTarget}</Badge> : null}
                </div>

                <div className="rounded-2xl border border-brand-200 bg-brand-50 px-4 py-4 text-sm leading-6 text-brand-800 dark:border-brand-900 dark:bg-brand-950/50 dark:text-brand-200">
                    <div className="flex items-center gap-2 font-semibold">
                        <ShieldCheck size={16} />
                        Quy tắc truy cập nội bộ
                    </div>
                    <p className="mt-2">
                        Teacher và admin chỉ hoạt động khi email thuộc miền {INTERNAL_EMAIL_DOMAIN}. Nếu tài khoản chưa được admin phân quyền, backend sẽ giữ
                        nguyên role mặc định là student.
                    </p>
                </div>

                <p className="text-sm text-gray-600 dark:text-gray-300">
                    {hasExplicitBootstrap && requestedRole
                        ? isBootstrapping
                            ? `Đang khởi tạo phiên ${requestedRole} trước khi chuyển trang...`
                            : activeSession
                              ? `Đã xác nhận ${activeSession.user.email}. Hệ thống đang điều hướng...`
                              : 'Đang chờ bootstrap hoàn tất...'
                        : activeSession
                          ? `Đã xác nhận ${activeSession.user.email}. Hệ thống đang điều hướng...`
                          : 'Đang kiểm tra cookie phiên sau khi hoàn tất Google OAuth...'}
                </p>
            </Card>
        </div>
    )
}
