import type {
    AnswerReference,
    AnswerWarning,
    Conversation,
    ConversationDto,
    Message,
    MessageDto,
} from '@/entities/chat/types'

export function mapReferenceDto(dto: MessageDto['references'][number]): AnswerReference {
    return {
        id: dto.id,
        title: dto.title,
        href: dto.href,
        excerpt: dto.excerpt,
        statusLabel: dto.status_label,
    }
}

export function mapWarningDto(dto: MessageDto['warnings'][number]): AnswerWarning {
    return {
        code: dto.code,
        message: dto.message,
    }
}

export function mapMessageDto(dto: MessageDto): Message {
    return {
        id: dto.id,
        role: dto.role,
        content: dto.content,
        createdAt: dto.created_at,
        confidence: dto.confidence,
        references: dto.references.map(mapReferenceDto),
        warnings: dto.warnings.map(mapWarningDto),
    }
}

export function mapConversationDto(dto: ConversationDto): Conversation {
    return {
        id: dto.id,
        title: dto.title,
        updatedAt: dto.updated_at,
        messages: dto.messages.map(mapMessageDto),
    }
}
