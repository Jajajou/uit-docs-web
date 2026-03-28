export interface AnswerReference {
    id: string
    title: string
    href: string
    excerpt: string
    statusLabel: string
}

export interface AnswerWarning {
    code: string
    message: string
}

export interface Message {
    id: string
    role: 'user' | 'assistant' | 'system'
    content: string
    createdAt: string
    confidence?: number
    references: AnswerReference[]
    warnings: AnswerWarning[]
}

export interface Conversation {
    id: string
    title: string
    updatedAt: string
    messages: Message[]
}

export interface AnswerReferenceDto {
    id: string
    title: string
    href: string
    excerpt: string
    status_label: string
}

export interface AnswerWarningDto {
    code: string
    message: string
}

export interface MessageDto {
    id: string
    role: 'user' | 'assistant' | 'system'
    content: string
    created_at: string
    confidence?: number
    references: AnswerReferenceDto[]
    warnings: AnswerWarningDto[]
}

export interface ConversationDto {
    id: string
    title: string
    updated_at: string
    messages: MessageDto[]
}

export interface ChatResponseDto {
    conversation_id: string
    message: MessageDto
}
