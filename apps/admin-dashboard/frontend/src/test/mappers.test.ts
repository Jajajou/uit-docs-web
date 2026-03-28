import { describe, expect, it } from 'vitest'
import {
    mapAdminUserDtoToAdminUser,
    mapAuditLogEntryDtoToAuditLogEntry,
    mapRolePolicyDtoToRolePolicy,
    mapSystemSettingDtoToSystemSetting,
} from '@/entities/admin/mappers'
import { mapSessionDtoToSession } from '@/entities/auth/mappers'
import { mapDocumentDtoToDocument } from '@/entities/documents/mappers'
import { mapReviewTaskDtoToReviewTask } from '@/entities/reviews/mappers'
import {
    adminUserFixtures,
    auditLogFixtures,
    rolePolicyFixtures,
    systemSettingFixtures,
} from '@/mocks/fixtures/admin'
import { documentFixtures } from '@/mocks/fixtures/documents'
import { sessionFixtures } from '@/mocks/fixtures/auth'
import { reviewFixtures } from '@/mocks/fixtures/reviews'

describe('DTO mappers', () => {
    it('maps session DTO into session domain model', () => {
        const session = mapSessionDtoToSession(sessionFixtures.operator)

        expect(session.user.role).toBe('operator')
        expect(session.user.avatarInitials).toBe('LO')
    })

    it('groups document metadata into domain slices', () => {
        const document = mapDocumentDtoToDocument(documentFixtures[0])

        expect(document.temporal.documentType).toBe('regulation')
        expect(document.system.versionNumber).toBe(2)
        expect(document.supplemental.issuingUnit).toBe('Phong Dao tao Dai hoc')
        expect(document.versionHistory[0]).toMatchObject({
            versionNumber: 2,
            isCurrent: true,
            changeHighlights: expect.any(Array),
        })
        expect(document.traceability?.reviewedByName).toBe('Le Thi Operator')
        expect(document.activityHistory).toHaveLength(0)
    })

    it('maps review task linkage into domain model', () => {
        const reviewTask = mapReviewTaskDtoToReviewTask(reviewFixtures[1])

        expect(reviewTask.submissionId).toBe('sub-002')
        expect(reviewTask.publishedDocumentId).toBe('doc-004')
        expect(reviewTask.visibilityScope).toBe('public')
    })

    it('maps admin user and role policy DTOs into domain models', () => {
        const adminUser = mapAdminUserDtoToAdminUser(adminUserFixtures[1])
        const rolePolicy = mapRolePolicyDtoToRolePolicy(rolePolicyFixtures[2])

        expect(adminUser.lastActiveAt).toBe(adminUserFixtures[1].last_active_at)
        expect(rolePolicy.allowedRoutes.length).toBeGreaterThan(0)
        expect(rolePolicy.requiresInternalEmail).toBe(true)
    })

    it('maps settings and audit logs DTOs into domain models', () => {
        const setting = mapSystemSettingDtoToSystemSetting(systemSettingFixtures[0])
        const auditLog = mapAuditLogEntryDtoToAuditLogEntry(auditLogFixtures[0])

        expect(setting.isSensitive).toBe(false)
        expect(auditLog.targetType).toBe('submission')
        expect(auditLog.createdAt).toBe(auditLogFixtures[0].created_at)
    })
})
