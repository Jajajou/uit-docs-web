import type { Session, SessionDto, SsoProviderMetadata, SsoProviderMetadataDto, User } from '@/entities/auth/types'
import { normalizeRole } from '@/entities/auth/roles'

export function mapUserDtoToUser(dto: SessionDto['user']): User {
    return {
        id: dto.id,
        name: dto.name,
        email: dto.email,
        role: normalizeRole(dto.role),
        department: dto.department,
        avatarInitials: dto.avatar_initials,
    }
}

export function mapSessionDtoToSession(dto: SessionDto): Session {
    return {
        id: dto.session_id,
        status: dto.status,
        user: mapUserDtoToUser(dto.user),
    }
}

export function mapSsoProviderMetadataDto(dto: SsoProviderMetadataDto): SsoProviderMetadata {
    return {
        mode: dto.mode,
        providerName: dto.provider_name,
        usesLocalEmulator: dto.uses_local_emulator,
        configured: dto.configured,
        authorizationEndpoint: dto.authorization_endpoint,
        callbackPath: dto.callback_path,
        roleClaim: dto.role_claim,
        groupClaim: dto.group_claim,
        emailClaim: dto.email_claim,
        defaultScope: dto.default_scope,
    }
}
