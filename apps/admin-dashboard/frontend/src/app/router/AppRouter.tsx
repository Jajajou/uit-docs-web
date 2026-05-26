import { Suspense, lazy } from 'react'
import { Route, Routes } from 'react-router-dom'

import { RouteGuard } from '@/app/guards/RouteGuard'
import RouteLoadingFallback from '@/app/router/RouteLoadingFallback'
import {
    loadAppLayout,
    loadAuthLayout,
    loadChatPage,
    loadLibraryPage,
    loadDocumentDetailPage,
    loadLoginPage,
    loadAuthCallbackPage,
    loadUploadPage,
    loadPortalOverviewPage,
    loadSubmissionsPage,
    loadSubmissionDetailPage,
    loadReviewPage,
    loadJobsPage,
    loadManagerPage,
    loadForbiddenPage,
    loadNotFoundPage,
} from '@/app/router/routeModules'

const AppLayout = lazy(loadAppLayout)
const AuthLayout = lazy(loadAuthLayout)

const ChatPage = lazy(loadChatPage)
const LibraryPage = lazy(loadLibraryPage)
const DocumentDetailPage = lazy(loadDocumentDetailPage)

const LoginPage = lazy(loadLoginPage)
const AuthCallbackPage = lazy(loadAuthCallbackPage)

const UploadPage = lazy(loadUploadPage)
const PortalOverviewPage = lazy(loadPortalOverviewPage)
const SubmissionsPage = lazy(loadSubmissionsPage)
const SubmissionDetailPage = lazy(loadSubmissionDetailPage)
const ReviewPage = lazy(loadReviewPage)
const JobsPage = lazy(loadJobsPage)
const ManagerPage = lazy(loadManagerPage)

const ForbiddenPage = lazy(loadForbiddenPage)
const NotFoundPage = lazy(loadNotFoundPage)

export default function AppRouter() {
    return (
        <Suspense fallback={<RouteLoadingFallback />}>
            <Routes>
                <Route element={<AppLayout />}>
                    <Route path="/" element={<ChatPage />} />
                    <Route path="/chat" element={<ChatPage />} />
                    <Route path="/documents" element={<LibraryPage />} />
                    <Route path="/library" element={<LibraryPage />} />
                    <Route path="/portal/library" element={<LibraryPage />} />
                    <Route path="/documents/:id" element={<DocumentDetailPage />} />

                    {/* Guarded App Routes */}
                    <Route element={<RouteGuard allowedRoles={['teacher', 'admin']} />}>
                        <Route path="/portal" element={<PortalOverviewPage />} />
                        <Route path="/knowledge" element={<UploadPage />} />
                        <Route path="/upload" element={<UploadPage />} />
                        <Route path="/portal/upload" element={<UploadPage />} />
                        <Route path="/submissions" element={<SubmissionsPage />} />
                        <Route path="/portal/submissions" element={<SubmissionsPage />} />
                        <Route path="/submissions/:id" element={<SubmissionDetailPage />} />
                        <Route path="/portal/submissions/:id" element={<SubmissionDetailPage />} />
                    </Route>

                    <Route element={<RouteGuard allowedRoles={['admin']} />}>
                        <Route path="/review" element={<ReviewPage />} />
                        <Route path="/portal/review" element={<ReviewPage />} />
                        <Route path="/jobs" element={<JobsPage />} />
                        <Route path="/portal/jobs" element={<JobsPage />} />
                        <Route path="/manager" element={<ManagerPage />} />
                    </Route>
                </Route>

                <Route element={<AuthLayout />}>
                    <Route path="/auth/login" element={<LoginPage />} />
                    <Route path="/auth/callback" element={<AuthCallbackPage />} />
                </Route>

                <Route path="/403" element={<ForbiddenPage />} />
                <Route path="*" element={<NotFoundPage />} />
            </Routes>
        </Suspense>
    )
}
