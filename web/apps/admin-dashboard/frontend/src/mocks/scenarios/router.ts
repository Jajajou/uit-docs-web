import { isRole, isRoleDto, normalizeRole } from '@/entities/auth/roles'
import type { Role, SsoProviderMetadataDto } from '@/entities/auth/types'
import type { AuditLogEntryDto, AdminUserDto, RolePolicyDto, SystemSettingDto } from '@/entities/admin/types'
import type { ChatResponseDto, ConversationDto } from '@/entities/chat/types'
import type { DocumentDto } from '@/entities/documents/types'
import type { JobDto } from '@/entities/jobs/types'
import type { ReviewTaskDto } from '@/entities/reviews/types'
import type { SubmissionDto } from '@/entities/submissions/types'
import { ApiClientError } from '@/shared/api/error'
import {
    adminUserFixtures,
    auditLogFixtures,
    denseAuditLogFixtures,
    nonCompliantAdminUserFixtures,
    rolePolicyFixtures,
    systemSettingFixtures,
} from '@/mocks/fixtures/admin'
import { sessionFixtures } from '@/mocks/fixtures/auth'
import { conversationFixtures } from '@/mocks/fixtures/chat'
import { documentFixtures } from '@/mocks/fixtures/documents'
import { jobFixtures } from '@/mocks/fixtures/jobs'
import { reviewFixtures } from '@/mocks/fixtures/reviews'
import { submissionFixtures } from '@/mocks/fixtures/submissions'
import type { MockHttpError, MockHttpResponse, MockRequestDescriptor, MockScenario } from '@/mocks/scenarios/types'

type MockConversationRecord = ConversationDto & { owner_key?: string }

interface MockWorkspaceState {
    documents: DocumentDto[]
    submissions: SubmissionDto[]
    reviews: ReviewTaskDto[]
    jobs: JobDto[]
    adminUsers: AdminUserDto[]
    rolePolicies: RolePolicyDto[]
    systemSettings: SystemSettingDto[]
    auditLogs: AuditLogEntryDto[]
    conversations: MockConversationRecord[]
}

const INTERNAL_EMAIL_DOMAIN = '@gm.uit.edu.vn'
const INTERNAL_ROLES: Role[] = ['teacher', 'admin']

function clone<T>(value: T): T {
    return structuredClone(value)
}

function createState(): MockWorkspaceState {
    return {
        documents: clone(documentFixtures),
        submissions: clone(submissionFixtures),
        reviews: clone(reviewFixtures),
        jobs: clone(jobFixtures),
        adminUsers: clone(adminUserFixtures),
        rolePolicies: clone(rolePolicyFixtures),
        systemSettings: clone(systemSettingFixtures),
        auditLogs: clone(auditLogFixtures),
        conversations: clone(conversationFixtures),
    }
}

let state = createState()

export function resetMockScenarioState() {
    state = createState()
}

function toScenario(value: unknown): MockScenario {
    const allowed: MockScenario[] = [
        'happy',
        'empty',
        'error',
        'auth-error',
        'duplicate-upload',
        'low-confidence',
        'archived-doc',
        'failed-job',
        'non-compliant-internal-email',
        'dense-audit-history',
        'forbidden',
    ]

    if (typeof value === 'string' && allowed.includes(value as MockScenario)) {
        return value as MockScenario
    }

    return 'happy'
}

function createError(error: MockHttpError, requestId: string): never {
    throw new ApiClientError({
        ...error,
        requestId,
    })
}

function getRoleFromHeaders(headers: Record<string, string> | undefined): Role {
    const role = headers?.['x-demo-role']
    return isRole(role) ? role : 'student'
}

function getConversationOwnerKey(request: MockRequestDescriptor) {
    return `role:${getRoleFromHeaders(request.headers)}`
}

function toConversationDto(conversation: MockConversationRecord): ConversationDto {
    const { owner_key: _ownerKey, ...payload } = conversation
    return payload
}

function getRoleFromPayload(value: unknown): Role | null {
    if (isRole(value) || isRoleDto(value)) {
        return normalizeRole(value)
    }

    return null
}

function getScenario(request: MockRequestDescriptor) {
    return toScenario(request.params?.scenario)
}

function currentIsoTime() {
    return new Date().toISOString()
}

function buildDocumentVersionEntry(document: DocumentDto, versionNumber: number, createdAt: string, createdByName: string, changeSummary: string) {
    return {
        id: `${document.id}-v${versionNumber}`,
        version_number: versionNumber,
        created_at: createdAt,
        created_by_name: createdByName,
        change_summary: changeSummary,
        file_source: document.system_metadata.file_source,
        content_hash: document.system_metadata.content_hash,
        is_current: true,
        source_submission_id: null,
        source_review_id: null,
        change_highlights: [],
    }
}

function buildTemporalChangeHighlights(
    previousTemporal: unknown,
    nextTemporal: unknown,
    visibilityScope: string,
) {
    const highlights: string[] = []
    const previous = (typeof previousTemporal === 'object' && previousTemporal !== null ? previousTemporal : {}) as Record<string, unknown>
    const next = (typeof nextTemporal === 'object' && nextTemporal !== null ? nextTemporal : {}) as Record<string, unknown>

    const pushIfChanged = (key: string, label: string, format?: (value: unknown) => string) => {
        const formatter = format ?? ((value: unknown) => String(value ?? ''))
        const before = formatter(previous[key])
        const after = formatter(next[key])
        if (after && before !== after) {
            highlights.push(`${label} updated to ${after}.`)
        }
    }

    pushIfChanged('document_type', 'Document type')
    pushIfChanged('valid_from', 'Valid from')
    pushIfChanged('valid_until', 'Valid until')
    pushIfChanged('academic_year', 'Academic year')
    pushIfChanged('cohort_years', 'Cohort coverage', (value) => Array.isArray(value) ? value.join(', ') : '')

    highlights.push(
        visibilityScope === 'public'
            ? 'Marked as eligible for public student-facing citation.'
            : 'Retained for internal staff use only.',
    )

    return highlights.filter(Boolean).slice(0, 4)
}

function buildDocumentActivityEntry(
    id: string,
    actorName: string,
    actorRole: Role,
    action: AuditLogEntryDto['action'],
    targetType: AuditLogEntryDto['target_type'],
    targetId: string,
    targetLabel: string,
    createdAt: string,
): AuditLogEntryDto {
    return {
        id,
        actor_name: actorName,
        actor_role: actorRole,
        action,
        target_type: targetType,
        target_id: targetId,
        target_label: targetLabel,
        created_at: createdAt,
    }
}

function ensureRoleAllowed(request: MockRequestDescriptor, allowedRoles: Role[]) {
    const role = getRoleFromHeaders(request.headers)

    if (!allowedRoles.includes(role)) {
        createError(
            {
                code: 'forbidden',
                message: 'Access denied for this route.',
                status: 403,
            },
            request.requestId,
        )
    }

    return role
}

function isInternalDomainCompliant(role: Role, email: string) {
    return !INTERNAL_ROLES.includes(role) || email.toLowerCase().endsWith(INTERNAL_EMAIL_DOMAIN)
}

function getHappyState() {
    return state
}

function buildScenarioUsers(scenario: MockScenario) {
    if (scenario === 'non-compliant-internal-email') {
        return clone(nonCompliantAdminUserFixtures)
    }

    return clone(getHappyState().adminUsers)
}

function buildScenarioDocuments(scenario: MockScenario) {
    if (scenario === 'archived-doc') {
        return clone(getHappyState().documents.filter((document) => document.system_metadata.is_archived))
    }

    return clone(getHappyState().documents)
}

function buildScenarioJobs(scenario: MockScenario) {
    if (scenario === 'failed-job') {
        return clone(getHappyState().jobs.filter((job) => job.status === 'failed'))
    }

    return clone(getHappyState().jobs)
}

function buildScenarioAuditLogs(scenario: MockScenario) {
    if (scenario === 'dense-audit-history') {
        return clone(denseAuditLogFixtures)
    }

    return clone(getHappyState().auditLogs)
}

function resolveAuth(request: MockRequestDescriptor): MockHttpResponse {
    const scenario = getScenario(request)

    if (scenario === 'auth-error') {
        createError(
            {
                code: 'auth_fetch_failed',
                message: 'Unable to validate the current session.',
                status: 500,
            },
            request.requestId,
        )
    }

    if (scenario === 'forbidden') {
        createError(
            {
                code: 'forbidden',
                message: 'Access denied for this mock scenario.',
                status: 403,
            },
            request.requestId,
        )
    }

    const role = getRoleFromHeaders(request.headers)
    const session = clone(sessionFixtures[role])

    if (scenario === 'non-compliant-internal-email' && INTERNAL_ROLES.includes(role)) {
        session.user.email = `${role}@gmail.com`
    }

    return {
        status: 200,
        data: session,
    }
}

function resolveAuthBootstrap(request: MockRequestDescriptor): MockHttpResponse {
    const scenario = getScenario(request)
    const payload = typeof request.data === 'object' && request.data !== null ? (request.data as Record<string, unknown>) : {}
    const requestedRole = getRoleFromPayload(payload.role) ?? getRoleFromHeaders(request.headers)

    if (scenario === 'auth-error') {
        createError(
            {
                code: 'auth_fetch_failed',
                message: 'Unable to validate the current session.',
                status: 500,
            },
            request.requestId,
        )
    }

    if (scenario === 'forbidden') {
        createError(
            {
                code: 'forbidden',
                message: 'Access denied for this mock scenario.',
                status: 403,
            },
            request.requestId,
        )
    }

    if (scenario === 'non-compliant-internal-email' && INTERNAL_ROLES.includes(requestedRole)) {
        createError(
            {
                code: 'non_compliant_internal_email',
                message: 'The current session does not satisfy the institutional domain rule.',
                status: 403,
            },
            request.requestId,
        )
    }

    return {
        status: 200,
        data: clone(sessionFixtures[requestedRole]),
    }
}

function resolveSsoProviderMetadata(): MockHttpResponse<SsoProviderMetadataDto> {
    return {
        status: 200,
        data: {
            mode: 'emulator',
            provider_name: 'UIT Institutional SSO',
            uses_local_emulator: true,
            configured: true,
            authorization_endpoint: null,
            callback_path: '/api/auth/sso/callback',
            role_claim: 'role',
            group_claim: 'groups',
            email_claim: 'email',
            default_scope: 'openid profile email groups',
        },
    }
}

function resolveDocuments(request: MockRequestDescriptor): MockHttpResponse {
    const scenario = getScenario(request)

    if (scenario === 'error') {
        createError(
            {
                code: 'document_fetch_failed',
                message: 'Unable to load document library.',
                status: 500,
            },
            request.requestId,
        )
    }

    if (scenario === 'empty') {
        return {
            status: 200,
            data: { documents: [] },
        }
    }

    return {
        status: 200,
        data: { documents: buildScenarioDocuments(scenario) },
    }
}

function resolveDocumentDetail(request: MockRequestDescriptor): MockHttpResponse {
    const scenario = getScenario(request)
    const documentId = request.pathname.split('/').pop()
    const document = buildScenarioDocuments(scenario).find((entry) => entry.id === documentId)

    if (!document) {
        createError(
            {
                code: 'document_not_found',
                message: 'Document not found.',
                status: 404,
            },
            request.requestId,
        )
    }

    return {
        status: 200,
        data: { document },
    }
}

function resolveArchiveDocument(request: MockRequestDescriptor): MockHttpResponse {
    const actorRole = ensureRoleAllowed(request, ['admin'])
    const documentId = request.pathname.split('/')[2]
    const document = getHappyState().documents.find((entry) => entry.id === documentId)

    if (!document) {
        createError(
            {
                code: 'document_not_found',
                message: 'Document not found.',
                status: 404,
            },
            request.requestId,
        )
    }

    const now = currentIsoTime()
    document.lifecycle_status = 'archived'
    document.system_metadata.is_archived = true
    document.updated_at = now
    document.system_metadata.indexed_at = now

    const auditEntry = buildDocumentActivityEntry(
        `audit-${request.requestId.slice(0, 6)}`,
        'Tran Van Admin',
        actorRole,
        'archive_document',
        'document',
        document.id,
        document.title,
        now,
    )

    getHappyState().auditLogs.unshift(auditEntry)
    document.activity_history = [auditEntry, ...(document.activity_history ?? [])]

    return {
        status: 200,
        data: { document: clone(document) },
    }
}

function resolveReindexDocument(request: MockRequestDescriptor): MockHttpResponse {
    const actorRole = ensureRoleAllowed(request, ['admin'])
    const documentId = request.pathname.split('/')[2]
    const document = getHappyState().documents.find((entry) => entry.id === documentId)

    if (!document) {
        createError(
            {
                code: 'document_not_found',
                message: 'Document not found.',
                status: 404,
            },
            request.requestId,
        )
    }

    const now = currentIsoTime()
    document.processing_status = 'indexing'
    document.updated_at = now

    getHappyState().jobs.unshift({
        id: `job-${request.requestId.slice(0, 6)}`,
        type: 'indexing',
        status: 'indexing',
        progress: 12,
        related_title: document.title,
        started_at: now,
        updated_at: now,
        message: 'Reindex triggered from document detail action.',
    })

    const auditEntry = buildDocumentActivityEntry(
        `audit-${request.requestId.slice(0, 6)}`,
        'Tran Van Admin',
        actorRole,
        'reindex_document',
        'document',
        document.id,
        document.title,
        now,
    )

    getHappyState().auditLogs.unshift(auditEntry)
    document.activity_history = [auditEntry, ...(document.activity_history ?? [])]

    return {
        status: 200,
        data: { document: clone(document) },
    }
}

function resolveSubmissions(request: MockRequestDescriptor): MockHttpResponse {
    const scenario = getScenario(request)

    if (scenario === 'empty') {
        return {
            status: 200,
            data: { submissions: [] },
        }
    }

    return {
        status: 200,
        data: { submissions: clone(getHappyState().submissions) },
    }
}

function resolveSubmissionDetail(request: MockRequestDescriptor): MockHttpResponse {
    const scenario = getScenario(request)
    const submissionId = request.pathname.split('/').pop()
    const submission = clone(getHappyState().submissions).find((entry) => entry.id === submissionId)

    if (scenario === 'empty' || !submission) {
        createError(
            {
                code: 'submission_not_found',
                message: 'Submission not found.',
                status: 404,
            },
            request.requestId,
        )
    }

    return {
        status: 200,
        data: { submission },
    }
}

function buildSubmissionFromRequest(request: MockRequestDescriptor, sourceType: SubmissionDto['source_type']) {
    const scenario = getScenario(request)

    if (scenario === 'duplicate-upload') {
        createError(
            {
                code: 'duplicate_document',
                message: 'A document with the same content hash already exists.',
                status: 409,
                details: {
                    conflictingDocumentId: 'doc-001',
                },
            },
            request.requestId,
        )
    }

    const template = clone(submissionFixtures[0])
    const now = currentIsoTime()
    const payload = typeof request.data === 'object' && request.data !== null ? request.data as Record<string, unknown> : {}
    const title = String(payload.title || template.title)
    const submission: SubmissionDto = {
        ...template,
        id: `sub-${sourceType}-${request.requestId.slice(0, 6)}`,
        title,
        source_type: sourceType,
        created_at: now,
        updated_at: now,
        linked_document_id: null,
        processing_status: 'uploading',
        lifecycle_status: 'pending_review',
        temporal_metadata:
            scenario === 'low-confidence'
                ? {
                    ...template.temporal_metadata,
                    document_type: 'other',
                    temporal_confidence: 0,
                    temporal_reasoning: '',
                    document_number: null,
                }
                : template.temporal_metadata,
        system_metadata: {
            ...template.system_metadata,
            file_source: String(payload.url || payload.fileName || template.system_metadata.file_source),
            indexed_at: now,
            version_number: 1,
        },
        supplemental_metadata: {
            title,
            issuing_unit: String(payload.issuingUnit || template.supplemental_metadata.issuing_unit),
            tags: Array.isArray(payload.tags) ? payload.tags.map(String) : template.supplemental_metadata.tags,
            visibility_scope: payload.visibilityScope === 'public' ? 'public' : payload.visibilityScope === 'internal' ? 'internal' : template.supplemental_metadata.visibility_scope,
            notes: String(payload.notes || template.supplemental_metadata.notes),
        },
        traceability: {
            review_task_id: `review-${request.requestId.slice(0, 6)}`,
            published_document_id: null,
            reviewed_by_name: 'Tran Van Admin',
            published_at: null,
            publication_reason: String(payload.notes || template.supplemental_metadata.notes),
        },
    }

    if (scenario === 'happy') {
        getHappyState().submissions.unshift(clone(submission))
        getHappyState().jobs.unshift({
            id: `job-${request.requestId.slice(0, 6)}`,
            type: 'upload',
            status: 'uploading',
            progress: 15,
            related_title: title,
            started_at: now,
            updated_at: now,
            message: 'Submission accepted and queued for extraction.',
        })
        getHappyState().reviews.unshift({
            id: submission.traceability?.review_task_id ?? `review-${request.requestId.slice(0, 6)}`,
            submission_id: submission.id,
            published_document_id: null,
            title,
            source_type: sourceType,
            visibility_scope: submission.supplemental_metadata.visibility_scope,
            submitted_by_name: 'Pham Van Teacher',
            submitted_by_email: 'teacher@gm.uit.edu.vn',
            reviewer_name: 'Tran Van Admin',
            status: 'pending_review',
            confidence: submission.temporal_metadata.temporal_confidence,
            created_at: now,
            extracted_temporal_metadata: clone(submission.temporal_metadata),
            edited_temporal_metadata: clone(submission.temporal_metadata),
            reason: String(payload.notes || 'Waiting for reviewer confirmation.'),
        })
        getHappyState().auditLogs.unshift({
            id: `audit-${request.requestId.slice(0, 6)}`,
            actor_name: 'Pham Van Teacher',
            actor_role: getRoleFromHeaders(request.headers),
            action: 'upload_submission',
            target_type: 'submission',
            target_id: submission.id,
            target_label: title,
            created_at: now,
        })
    }

    return {
        status: 202,
        data: { submission },
    }
}

function resolveReviews(request: MockRequestDescriptor): MockHttpResponse {
    const scenario = getScenario(request)

    return {
        status: 200,
        data: {
            tasks: scenario === 'empty' ? [] : clone(getHappyState().reviews),
        },
    }
}

function resolveReviewDecision(request: MockRequestDescriptor): MockHttpResponse {
    const reviewId = request.pathname.split('/')[2]
    const review = getHappyState().reviews.find((entry) => entry.id === reviewId)

    if (!review) {
        createError(
            {
                code: 'review_not_found',
                message: 'Review task not found.',
                status: 404,
            },
            request.requestId,
        )
    }

    const payload = typeof request.data === 'object' && request.data !== null ? request.data as Record<string, unknown> : {}
    const nextStatus = (payload.status as ReviewTaskDto['status']) ?? review.status
    const now = currentIsoTime()
    const actorRole = getRoleFromHeaders(request.headers)

    review.status = nextStatus
    review.reason = typeof payload.reason === 'string' && payload.reason.trim().length > 0 ? payload.reason : review.reason
    if (payload.edited_temporal_metadata && typeof payload.edited_temporal_metadata === 'object') {
        review.edited_temporal_metadata = clone(payload.edited_temporal_metadata as ReviewTaskDto['edited_temporal_metadata'])
    }

    const submission = getHappyState().submissions.find((entry) => entry.id === review.submission_id)
    if (submission) {
        submission.lifecycle_status = nextStatus
        submission.updated_at = now
        submission.temporal_metadata = clone(review.edited_temporal_metadata)
        submission.processing_status = nextStatus === 'approved' ? 'completed' : nextStatus === 'rejected' ? 'failed' : 'indexing'

        if (nextStatus === 'approved') {
            const documentId = review.published_document_id ?? `doc-${request.requestId.slice(0, 6)}`
            review.published_document_id = documentId
            submission.linked_document_id = documentId
            const existingDocument = getHappyState().documents.find((entry) => entry.id === documentId)
            const nextVersionNumber = (existingDocument?.system_metadata.version_number ?? 0) + 1
            const documentPayload: DocumentDto = {
                id: documentId,
                title: submission.title,
                owner_name: review.submitted_by_name,
                owner_email: review.submitted_by_email,
                lifecycle_status: 'approved',
                processing_status: 'completed',
                created_at: submission.created_at,
                updated_at: now,
                temporal_metadata: clone(review.edited_temporal_metadata),
                system_metadata: {
                    ...clone(submission.system_metadata),
                    version_number: nextVersionNumber,
                    indexed_at: now,
                },
                supplemental_metadata: clone(submission.supplemental_metadata),
                traceability: {
                    source_submission_id: submission.id,
                    source_review_id: review.id,
                    reviewed_by_name: review.reviewer_name,
                    published_at: now,
                    publication_reason: review.reason,
                },
                version_history: [
                    {
                        ...buildDocumentVersionEntry(
                        {
                            ...(existingDocument ?? {
                                ...documentFixtures[0],
                                id: documentId,
                                system_metadata: {
                                    ...clone(submission.system_metadata),
                                    version_number: nextVersionNumber,
                                    indexed_at: now,
                                },
                            }),
                            id: documentId,
                            system_metadata: {
                                ...clone(submission.system_metadata),
                                version_number: nextVersionNumber,
                                indexed_at: now,
                            },
                        },
                        nextVersionNumber,
                        now,
                        actorRole === 'admin' ? 'Tran Van Admin' : review.reviewer_name,
                        review.reason,
                    ),
                        source_submission_id: submission.id,
                        source_review_id: review.id,
                        change_highlights: buildTemporalChangeHighlights(
                            existingDocument?.temporal_metadata ?? review.extracted_temporal_metadata,
                            review.edited_temporal_metadata as unknown as Record<string, unknown>,
                            submission.supplemental_metadata.visibility_scope,
                        ),
                    },
                    ...((existingDocument?.version_history ?? []).map((entry) => ({ ...entry, is_current: false }))),
                ],
                activity_history: clone(existingDocument?.activity_history ?? []),
            }

            if (existingDocument) {
                Object.assign(existingDocument, documentPayload)
            } else {
                getHappyState().documents.unshift(documentPayload)
            }
        } else {
            review.published_document_id = nextStatus === 'rejected' ? null : review.published_document_id
            submission.linked_document_id = null
        }

        submission.traceability = {
            review_task_id: review.id,
            published_document_id: review.published_document_id,
            reviewed_by_name: review.reviewer_name,
            published_at: nextStatus === 'approved' ? now : null,
            publication_reason: review.reason,
        }
    }

    let auditAction: AuditLogEntryDto['action']
    switch (nextStatus) {
        case 'approved':
            auditAction = 'approve_review'
            break
        case 'rejected':
            auditAction = 'reject_review'
            break
        default:
            auditAction = 'request_changes'
            break
    }

    const auditEntry = buildDocumentActivityEntry(
        `audit-${request.requestId.slice(0, 6)}`,
        'Tran Van Admin',
        actorRole,
        auditAction,
        'review',
        review.id,
        review.title,
        now,
    )

    getHappyState().auditLogs.unshift(auditEntry)
    if (nextStatus === 'approved' && review.published_document_id) {
        const document = getHappyState().documents.find((entry) => entry.id === review.published_document_id)
        if (document) {
            document.activity_history = [auditEntry, ...(document.activity_history ?? [])]
        }
    }

    return {
        status: 200,
        data: {
            task: clone(review),
        },
    }
}

function resolveJobs(request: MockRequestDescriptor): MockHttpResponse {
    const scenario = getScenario(request)

    return {
        status: 200,
        data: { jobs: scenario === 'empty' ? [] : buildScenarioJobs(scenario) },
    }
}

function resolveRetryJob(request: MockRequestDescriptor): MockHttpResponse {
    const jobId = request.pathname.split('/')[2]
    const job = getHappyState().jobs.find((entry) => entry.id === jobId)

    if (!job) {
        createError(
            {
                code: 'job_not_found',
                message: 'Job not found.',
                status: 404,
            },
            request.requestId,
        )
    }

    job.status = 'indexing'
    job.progress = 15
    job.updated_at = currentIsoTime()
    job.message = 'Retry accepted by the mock contract.'

    return {
        status: 200,
        data: {
            job: clone(job),
            retry_accepted: true,
        },
    }
}

function resolveAdminUsers(request: MockRequestDescriptor): MockHttpResponse {
    const scenario = getScenario(request)

    if (scenario === 'error') {
        createError(
            {
                code: 'admin_user_fetch_failed',
                message: 'Unable to load admin users.',
                status: 500,
            },
            request.requestId,
        )
    }

    if (scenario === 'empty') {
        return {
            status: 200,
            data: { users: [] },
        }
    }

    return {
        status: 200,
        data: {
            users: buildScenarioUsers(scenario),
        },
    }
}

function resolvePatchAdminUser(request: MockRequestDescriptor): MockHttpResponse {
    const userId = request.pathname.split('/')[3]
    const user = getHappyState().adminUsers.find((entry) => entry.id === userId)

    if (!user) {
        createError(
            {
                code: 'admin_user_not_found',
                message: 'Admin user not found.',
                status: 404,
            },
            request.requestId,
        )
    }

    const payload = typeof request.data === 'object' && request.data !== null ? request.data as Record<string, unknown> : {}
    if (isRole(payload.role)) {
        user.role = payload.role
    }
    if (typeof payload.status === 'string') {
        user.status = payload.status as AdminUserDto['status']
    }
    if (typeof payload.scope === 'string') {
        user.scope = payload.scope as AdminUserDto['scope']
    }
    user.last_active_at = currentIsoTime()
    user.is_internal_domain_compliant = isInternalDomainCompliant(normalizeRole(user.role), user.email)

    getHappyState().auditLogs.unshift({
        id: `audit-${request.requestId.slice(0, 6)}`,
        actor_name: 'Tran Van Admin',
        actor_role: 'admin',
        action: 'role_switch',
        target_type: 'session',
        target_id: user.id,
        target_label: `${user.name} access profile updated`,
        created_at: user.last_active_at,
    })

    return {
        status: 200,
        data: { user: clone(user) },
    }
}

function resolveRolePolicies(request: MockRequestDescriptor): MockHttpResponse {
    const scenario = getScenario(request)

    if (scenario === 'error') {
        createError(
            {
                code: 'role_policy_fetch_failed',
                message: 'Unable to load role policies.',
                status: 500,
            },
            request.requestId,
        )
    }

    return {
        status: 200,
        data: {
            roles: scenario === 'empty' ? [] : clone(getHappyState().rolePolicies),
        },
    }
}

function resolveSystemSettings(request: MockRequestDescriptor): MockHttpResponse {
    const scenario = getScenario(request)

    if (scenario === 'error') {
        createError(
            {
                code: 'system_settings_fetch_failed',
                message: 'Unable to load system settings.',
                status: 500,
            },
            request.requestId,
        )
    }

    return {
        status: 200,
        data: {
            settings: scenario === 'empty' ? [] : clone(getHappyState().systemSettings),
        },
    }
}

function resolvePatchSystemSetting(request: MockRequestDescriptor): MockHttpResponse {
    const key = request.pathname.split('/')[3]
    const setting = getHappyState().systemSettings.find((entry) => entry.key === key)

    if (!setting) {
        createError(
            {
                code: 'system_setting_not_found',
                message: 'System setting not found.',
                status: 404,
            },
            request.requestId,
        )
    }

    const payload = typeof request.data === 'object' && request.data !== null ? request.data as Record<string, unknown> : {}
    setting.value = String(payload.value ?? setting.value)

    return {
        status: 200,
        data: { setting: clone(setting) },
    }
}

function resolveAuditLogs(request: MockRequestDescriptor): MockHttpResponse {
    const scenario = getScenario(request)

    if (scenario === 'error') {
        createError(
            {
                code: 'audit_logs_fetch_failed',
                message: 'Unable to load audit logs.',
                status: 500,
            },
            request.requestId,
        )
    }

    return {
        status: 200,
        data: { logs: scenario === 'empty' ? [] : buildScenarioAuditLogs(scenario) },
    }
}

function resolveConversations(request: MockRequestDescriptor): MockHttpResponse {
    const ownerKey = getConversationOwnerKey(request)
    return {
        status: 200,
        data: {
            conversations:
                getScenario(request) === 'empty'
                    ? []
                    : clone(
                        getHappyState()
                            .conversations.filter((conversation) => conversation.owner_key === ownerKey)
                            .map(toConversationDto),
                    ),
        },
    }
}

function resolveDeleteConversation(request: MockRequestDescriptor): MockHttpResponse {
    const segments = request.pathname.split('/')
    const conversationId = segments[segments.length - 1]
    const ownerKey = getConversationOwnerKey(request)

    if (!conversationId) {
        createError(
            {
                code: 'conversation_not_found',
                message: 'Conversation not found.',
                status: 404,
            },
            request.requestId,
        )
    }

    const state = getHappyState()
    const nextConversations = state.conversations.filter(
        (conversation) => !(conversation.id === conversationId && conversation.owner_key === ownerKey),
    )
    if (nextConversations.length === state.conversations.length) {
        createError(
            {
                code: 'conversation_not_found',
                message: 'Conversation not found.',
                status: 404,
            },
            request.requestId,
        )
    }

    state.conversations = nextConversations
    return { status: 204, data: undefined }
}

function resolveClearConversationsForOwner(request: MockRequestDescriptor): MockHttpResponse {
    const ownerKey = getConversationOwnerKey(request)
    getHappyState().conversations = getHappyState().conversations.filter((conversation) => conversation.owner_key !== ownerKey)
    return { status: 204, data: undefined }
}

function resolveChatResponse(request: MockRequestDescriptor): MockHttpResponse<ChatResponseDto> {
    const scenario = getScenario(request)
    const ownerKey = getConversationOwnerKey(request)
    const payload = typeof request.data === 'object' && request.data !== null ? request.data as Record<string, unknown> : {}
    const question = typeof payload.message === 'string' ? payload.message : 'Can you clarify the request?'
    const conversationId =
        typeof payload.conversationId === 'string' && payload.conversationId.trim()
            ? payload.conversationId
            : `conv-${request.requestId.slice(0, 8)}`

    if (scenario === 'error') {
        createError(
            {
                code: 'chat_failed',
                message: 'Unable to generate assistant response.',
                status: 500,
            },
            request.requestId,
        )
    }

    const reply = {
        id: `msg-${request.requestId.slice(0, 8)}`,
        role: 'assistant' as const,
        content:
            scenario === 'low-confidence'
                ? `Toi tim thay thong tin lien quan den: "${question}", nhung do tin cay dang thap va ban nen doi chieu them voi phong ban phu trach.`
                : `Day la phan hoi contract-backed cho cau hoi: "${question}". Assistant uu tien tai lieu moi, co nguon va canh bao khi can.`,
        created_at: currentIsoTime(),
        confidence: scenario === 'low-confidence' ? 0.35 : 0.86,
        references: [
            {
                id: 'ref-response-001',
                title: scenario === 'low-confidence' ? 'Thong bao hoc phi hoc ky 2' : 'Quy dinh hoc vu 2024-2025',
                href: scenario === 'low-confidence' ? '/documents/doc-002' : '/documents/doc-001',
                excerpt: 'Mock reference excerpt used for foundational frontend flows.',
                status_label: scenario === 'low-confidence' ? 'Pending review' : 'Approved',
            },
        ],
        warnings:
            scenario === 'low-confidence'
                ? [
                    {
                        code: 'low_confidence',
                        message: 'Assistant confidence is low because metadata is incomplete.',
                    },
                ]
                : [],
    }

    const state = getHappyState()
    let conversation = state.conversations.find((entry) => entry.id === conversationId)
    if (conversation && conversation.owner_key !== ownerKey) {
        createError(
            {
                code: 'conversation_not_found',
                message: 'Conversation not found.',
                status: 404,
            },
            request.requestId,
        )
    }
    if (conversation) {
        conversation.messages.push({
            id: `msg-user-${request.requestId.slice(0, 8)}`,
            role: 'user',
            content: question,
            created_at: currentIsoTime(),
            references: [],
            warnings: [],
        })
        conversation.messages.push(clone(reply))
        conversation.updated_at = reply.created_at
    } else {
        conversation = {
            id: conversationId,
            owner_key: ownerKey,
            title: question.slice(0, 64) || 'Cuoc tro chuyen moi',
            updated_at: reply.created_at,
            messages: [
                {
                    id: `msg-user-${request.requestId.slice(0, 8)}`,
                    role: 'user',
                    content: question,
                    created_at: currentIsoTime(),
                    references: [],
                    warnings: [],
                },
                clone(reply),
            ],
        }
        state.conversations.unshift(conversation)
    }

    return {
        status: 200,
        data: {
            conversation_id: conversationId,
            message: reply,
        },
    }
}

export async function resolveMockRequest(request: MockRequestDescriptor): Promise<MockHttpResponse> {
    const method = request.method.toLowerCase()

    if (method === 'post' && request.pathname === '/auth/bootstrap') return resolveAuthBootstrap(request)
    if (method === 'get' && request.pathname === '/auth/me') return resolveAuth(request)
    if (method === 'get' && request.pathname === '/auth/sso/metadata') return resolveSsoProviderMetadata()
    if (method === 'get' && request.pathname === '/documents') return resolveDocuments(request)
    if (method === 'get' && /^\/documents\/[^/]+$/.test(request.pathname)) return resolveDocumentDetail(request)
    if (method === 'post' && /^\/documents\/[^/]+\/archive$/.test(request.pathname)) return resolveArchiveDocument(request)
    if (method === 'post' && /^\/documents\/[^/]+\/reindex$/.test(request.pathname)) return resolveReindexDocument(request)
    if (method === 'get' && request.pathname === '/submissions') return resolveSubmissions(request)
    if (method === 'get' && /^\/submissions\/[^/]+$/.test(request.pathname)) return resolveSubmissionDetail(request)
    if (method === 'post' && request.pathname === '/uploads/file') return buildSubmissionFromRequest(request, 'file')
    if (method === 'post' && request.pathname === '/uploads/text') return buildSubmissionFromRequest(request, 'text')
    if (method === 'post' && request.pathname === '/uploads/url') return buildSubmissionFromRequest(request, 'url')
    if (method === 'get' && request.pathname === '/reviews') return resolveReviews(request)
    if (method === 'post' && /^\/reviews\/[^/]+\/decision$/.test(request.pathname)) return resolveReviewDecision(request)
    if (method === 'get' && request.pathname === '/jobs') return resolveJobs(request)
    if (method === 'post' && /^\/jobs\/[^/]+\/retry$/.test(request.pathname)) return resolveRetryJob(request)
    if (method === 'get' && request.pathname === '/admin/users') return resolveAdminUsers(request)
    if (method === 'patch' && /^\/admin\/users\/[^/]+$/.test(request.pathname)) return resolvePatchAdminUser(request)
    if (method === 'get' && request.pathname === '/admin/roles') return resolveRolePolicies(request)
    if (method === 'get' && request.pathname === '/admin/settings') return resolveSystemSettings(request)
    if (method === 'patch' && /^\/admin\/settings\/[^/]+$/.test(request.pathname)) return resolvePatchSystemSetting(request)
    if (method === 'get' && request.pathname === '/admin/audit-logs') return resolveAuditLogs(request)
    if (method === 'get' && request.pathname === '/chat/sessions') return resolveConversations(request)
    if (method === 'delete' && request.pathname === '/chat/sessions') return resolveClearConversationsForOwner(request)
    if (method === 'delete' && /^\/chat\/sessions\/[^/]+$/.test(request.pathname)) return resolveDeleteConversation(request)
    if (method === 'post' && request.pathname === '/chat/stream') return resolveChatResponse(request)

    createError(
        {
            code: 'mock_route_not_found',
            message: `No mock route defined for ${method.toUpperCase()} ${request.pathname}`,
            status: 404,
        },
        request.requestId,
    )
}
