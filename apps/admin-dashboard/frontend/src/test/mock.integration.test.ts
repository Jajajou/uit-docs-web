import { describe, expect, it } from 'vitest'
import { getAdminUsers, getAuditLogs, getRolePolicies, getSystemSettings, patchAdminUser, patchSystemSetting } from '@/entities/admin/api'
import { bootstrapSession, getSession, getSsoProviderMetadata } from '@/entities/auth/api'
import { useSessionStore } from '@/entities/auth/store'
import { archiveDocument, getDocumentById, getDocuments, reindexDocument } from '@/entities/documents/api'
import { getJobs, retryJob } from '@/entities/jobs/api'
import { applyReviewDecision, getReviewTasks } from '@/entities/reviews/api'
import { createUploadSubmission, getSubmissionById } from '@/entities/submissions/api'
import { ApiClientError } from '@/shared/api/error'

describe('mock contract integration', () => {
    it('creates upload submission successfully', async () => {
        const submission = await createUploadSubmission('/uploads/file', {
            sourceType: 'file',
            title: 'Mock upload',
            fileName: 'mock.pdf',
            issuingUnit: 'Phong Dao tao Dai hoc',
            visibilityScope: 'internal',
            tags: ['mock-upload'],
            notes: 'Created during mock integration test.',
        })

        expect(submission.processingStatus).toBe('uploading')
        expect(submission.title).toBe('Mock upload')
    })

    it('rejects duplicate uploads', async () => {
        await expect(
            createUploadSubmission(
                '/uploads/file',
                {
                    sourceType: 'file',
                    title: 'Duplicate upload',
                    fileName: 'duplicate.pdf',
                    issuingUnit: 'Phong Dao tao Dai hoc',
                    visibilityScope: 'internal',
                    tags: ['duplicate'],
                    notes: 'Expected duplicate flow.',
                },
                { scenario: 'duplicate-upload' },
            ),
        ).rejects.toBeInstanceOf(ApiClientError)
    })

    it('returns low-confidence extraction fallback values', async () => {
        const submission = await createUploadSubmission(
            '/uploads/text',
            {
                sourceType: 'text',
                title: 'Low confidence text',
                content: 'some free-form text',
                issuingUnit: 'Phong Cong tac Sinh vien',
                visibilityScope: 'public',
                tags: ['low-confidence'],
                notes: 'Expected low confidence flow.',
            },
            { scenario: 'low-confidence' },
        )

        expect(submission.temporal.documentType).toBe('other')
        expect(submission.temporal.confidence).toBe(0)
    })

    it('surfaces review task diff payloads', async () => {
        const tasks = await getReviewTasks()

        expect(tasks[0].extractedTemporal.cohortYears).not.toEqual(tasks[0].editedTemporal.cohortYears)
    })

    it('links approved submission, review task and published document', async () => {
        const submission = await getSubmissionById('sub-002')
        const tasks = await getReviewTasks()
        const reviewTask = tasks.find((task) => task.submissionId === submission.id && task.status === 'approved')
        const document = await getDocumentById('doc-004')

        expect(submission.linkedDocumentId).toBe('doc-004')
        expect(submission.traceability?.reviewTaskId).toBe('review-002')
        expect(reviewTask?.publishedDocumentId).toBe('doc-004')
        expect(document.lifecycleStatus).toBe('approved')
        expect(document.supplemental.visibilityScope).toBe('public')
        expect(document.traceability?.sourceSubmissionId).toBe('sub-002')
        expect(document.versionHistory[0].changeHighlights.length).toBeGreaterThan(0)
    })

    it('filters archived document scenario', async () => {
        const documents = await getDocuments({ scenario: 'archived-doc' })

        expect(documents).toHaveLength(1)
        expect(documents[0].system.isArchived).toBe(true)
    })

    it('returns failed job scenario', async () => {
        const jobs = await getJobs({ scenario: 'failed-job' })

        expect(jobs).toHaveLength(1)
        expect(jobs[0].status).toBe('failed')
    })

    it('accepts review decisions through the shared contract', async () => {
        const task = await applyReviewDecision('review-001', {
            status: 'approved',
            reason: 'Approved in test.',
        })

        expect(task.status).toBe('approved')
        expect(task.reason).toBe('Approved in test.')
    })

    it('accepts retry job mutations through the shared contract', async () => {
        const job = await retryJob('job-002')

        expect(job.status).toBe('indexing')
        expect(job.progress).toBe(15)
    })

    it('accepts document archive and reindex mutations through the shared contract', async () => {
        useSessionStore.getState().setRole('admin')

        try {
            const archived = await archiveDocument('doc-001')
            const reindexed = await reindexDocument('doc-002')

            expect(archived.lifecycleStatus).toBe('archived')
            expect(archived.system.isArchived).toBe(true)
            expect(reindexed.processingStatus).toBe('indexing')
        } finally {
            useSessionStore.getState().setRole('student')
        }
    })

    it('returns admin datasets from mock endpoints', async () => {
        const [users, roles, settings, logs] = await Promise.all([
            getAdminUsers(),
            getRolePolicies(),
            getSystemSettings(),
            getAuditLogs(),
        ])

        expect(users.length).toBeGreaterThan(0)
        expect(roles.some((policy) => policy.role === 'admin')).toBe(true)
        expect(settings.some((setting) => setting.group === 'chat')).toBe(true)
        expect(logs.some((entry) => entry.targetType === 'document')).toBe(true)
    })

    it('accepts admin patch mutations through the shared contract', async () => {
        const updatedUser = await patchAdminUser('usr-005', {
            role: 'teacher',
            status: 'active',
        })
        const updatedSetting = await patchSystemSetting('citation_policy', {
            value: 'Every student answer must cite an approved source.',
        })

        expect(updatedUser.role).toBe('teacher')
        expect(updatedUser.status).toBe('active')
        expect(updatedSetting.value).toContain('approved source')
    })

    it('surfaces auth lookup failures from the mock router', async () => {
        await expect(getSession({ scenario: 'auth-error' })).rejects.toBeInstanceOf(ApiClientError)
    })

    it('bootstraps auth sessions through the shared contract', async () => {
        const session = await bootstrapSession('admin')

        expect(session.user.role).toBe('admin')
        expect(session.user.email).toBe('admin@gm.uit.edu.vn')
    })

    it('returns SSO provider metadata from the shared auth contract', async () => {
        const metadata = await getSsoProviderMetadata()

        expect(metadata.mode).toBe('emulator')
        expect(metadata.usesLocalEmulator).toBe(true)
        expect(metadata.callbackPath).toBe('/api/auth/sso/callback')
    })

    it('returns non-compliant internal email sessions for access-control testing', async () => {
        useSessionStore.getState().setRole('teacher')

        try {
            const session = await getSession({ scenario: 'non-compliant-internal-email' })

            expect(session.user.role).toBe('teacher')
            expect(session.user.email).toBe('teacher@gmail.com')
        } finally {
            useSessionStore.getState().setRole('student')
        }
    })

    it('rejects non-compliant internal bootstrap attempts', async () => {
        await expect(bootstrapSession('teacher', { scenario: 'non-compliant-internal-email' })).rejects.toBeInstanceOf(ApiClientError)
    })

    it('surfaces non-compliant internal email scenario', async () => {
        const users = await getAdminUsers({ scenario: 'non-compliant-internal-email' })

        expect(users.some((user) => user.role === 'teacher' && !user.isInternalDomainCompliant)).toBe(true)
    })

    it('returns dense audit history scenario', async () => {
        const logs = await getAuditLogs({ scenario: 'dense-audit-history' })

        expect(logs.length).toBeGreaterThan(5)
        expect(logs.some((entry) => entry.action === 'login')).toBe(true)
    })
})
