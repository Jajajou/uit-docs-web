export type Role = 'student' | 'teacher' | 'admin'
export type RoleDto = 'guest' | 'student' | 'teacher' | 'lecturer' | 'operator' | 'admin'

export interface User {
    id: string
    name: string
    email: string
    role: Role
    department: string
    avatarInitials: string
}

export interface Session {
    id: string
    status: 'anonymous' | 'authenticated'
    user: User
}

export interface UserDto {
    id: string
    name: string
    email: string
    role: RoleDto
    department: string
    avatar_initials: string
}

export interface SessionDto {
    session_id: string
    status: 'anonymous' | 'authenticated'
    user: UserDto
}

export interface SsoProviderMetadata {
    mode: 'emulator' | 'external'
    providerName: string
    usesLocalEmulator: boolean
    configured: boolean
    authorizationEndpoint: string | null
    callbackPath: string
    roleClaim: string
    groupClaim: string
    emailClaim: string
    defaultScope: string
}

export interface SsoProviderMetadataDto {
    mode: 'emulator' | 'external'
    provider_name: string
    uses_local_emulator: boolean
    configured: boolean
    authorization_endpoint: string | null
    callback_path: string
    role_claim: string
    group_claim: string
    email_claim: string
    default_scope: string
}
