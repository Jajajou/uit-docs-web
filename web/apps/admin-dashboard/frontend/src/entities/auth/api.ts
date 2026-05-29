import { apiClient } from '@/shared/api/client'
import { serializeRole } from '@/entities/auth/roles'
import { mapSessionDtoToSession, mapSsoProviderMetadataDto } from '@/entities/auth/mappers'
import type { Role, Session, SessionDto, SsoProviderMetadata, SsoProviderMetadataDto } from '@/entities/auth/types'

export async function getSession(params?: { scenario?: string }): Promise<Session> {
    const response = await apiClient.get<SessionDto>('/auth/me', {
        params,
    })

    return mapSessionDtoToSession(response.data)
}

export async function bootstrapSession(role: Role, params?: { scenario?: string }): Promise<Session> {
    const response = await apiClient.post<SessionDto>(
        '/auth/bootstrap',
        { role: serializeRole(role) },
        {
            params,
        },
    )

    return mapSessionDtoToSession(response.data)
}

export async function logoutSession() {
    await apiClient.post('/auth/logout')
}

export async function getSsoProviderMetadata(): Promise<SsoProviderMetadata> {
    const response = await apiClient.get<SsoProviderMetadataDto>('/auth/sso/metadata')
    return mapSsoProviderMetadataDto(response.data)
}
