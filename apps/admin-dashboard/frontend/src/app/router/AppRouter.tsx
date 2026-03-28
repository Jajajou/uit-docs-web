import { Suspense, lazy } from 'react'
import { Route, Routes } from 'react-router-dom'

import { RouteGuard } from '@/app/guards/RouteGuard'
import RouteLoadingFallback from '@/app/router/RouteLoadingFallback'
import {
    loadAdminLayout,
    loadAuditLogsPage,
    loadAuthCallbackPage,
    loadAuthLayout,
    loadChatPage,
    loadDocumentDetailPage,
    loadForbiddenPage,
    loadHomePage,
    loadJobsPage,
    loadLibraryPage,
    loadLoginPage,
    loadNotFoundPage,
    loadPortalLayout,
    loadPortalOverviewPage,
    loadPublicLayout,
    loadReviewPage,
    loadRolesPage,
    loadSettingsPage,
    loadSubmissionDetailPage,
    loadSubmissionsPage,
    loadUploadPage,
    loadUsersPage,
} from '@/app/router/routeModules'

const PublicLayout = lazy(loadPublicLayout)
const AuthLayout = lazy(loadAuthLayout)
const PortalLayout = lazy(loadPortalLayout)
const AdminLayout = lazy(loadAdminLayout)

const HomePage = lazy(loadHomePage)
const ChatPage = lazy(loadChatPage)
const DocumentDetailPage = lazy(loadDocumentDetailPage)

const LoginPage = lazy(loadLoginPage)
const AuthCallbackPage = lazy(loadAuthCallbackPage)

const PortalOverviewPage = lazy(loadPortalOverviewPage)
const UploadPage = lazy(loadUploadPage)
const SubmissionsPage = lazy(loadSubmissionsPage)
const SubmissionDetailPage = lazy(loadSubmissionDetailPage)
const ReviewPage = lazy(loadReviewPage)
const LibraryPage = lazy(loadLibraryPage)
const JobsPage = lazy(loadJobsPage)

const UsersPage = lazy(loadUsersPage)
const RolesPage = lazy(loadRolesPage)
const SettingsPage = lazy(loadSettingsPage)
const AuditLogsPage = lazy(loadAuditLogsPage)

const ForbiddenPage = lazy(loadForbiddenPage)
const NotFoundPage = lazy(loadNotFoundPage)

export default function AppRouter() {
    return (
        <Suspense fallback={<RouteLoadingFallback />}>
            <Routes>
                <Route element={<PublicLayout />}>
                    <Route path="/" element={<HomePage />} />
                    <Route path="/chat" element={<ChatPage />} />
                    <Route path="/documents/:id" element={<DocumentDetailPage />} />
                </Route>

                <Route element={<AuthLayout />}>
                    <Route path="/auth/login" element={<LoginPage />} />
                    <Route path="/auth/callback" element={<AuthCallbackPage />} />
                </Route>

                <Route path="/portal" element={<PortalLayout />}>
                    <Route element={<RouteGuard allowedRoles={['lecturer', 'operator', 'admin']} />}>
                        <Route index element={<PortalOverviewPage />} />
                        <Route path="upload" element={<UploadPage />} />
                        <Route path="submissions" element={<SubmissionsPage />} />
                        <Route path="submissions/:id" element={<SubmissionDetailPage />} />
                    </Route>

                    <Route element={<RouteGuard allowedRoles={['operator', 'admin']} />}>
                        <Route path="review" element={<ReviewPage />} />
                        <Route path="library" element={<LibraryPage />} />
                        <Route path="jobs" element={<JobsPage />} />
                    </Route>
                </Route>

                <Route path="/admin" element={<AdminLayout />}>
                    <Route element={<RouteGuard allowedRoles={['admin']} />}>
                        <Route path="users" element={<UsersPage />} />
                        <Route path="roles" element={<RolesPage />} />
                        <Route path="settings" element={<SettingsPage />} />
                        <Route path="audit-logs" element={<AuditLogsPage />} />
                    </Route>
                </Route>

                <Route path="/403" element={<ForbiddenPage />} />
                <Route path="*" element={<NotFoundPage />} />
            </Routes>
        </Suspense>
    )
}
