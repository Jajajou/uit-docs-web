import { apiClient } from '@/shared/api/client'
import { mapConversationDto, mapMessageDto } from '@/entities/chat/mappers'
import type { ChatResponseDto, Conversation, ConversationDto, Message } from '@/entities/chat/types'

const CHAT_REQUEST_TIMEOUT_MS = 90000

export async function getConversations(params?: { scenario?: string }): Promise<Conversation[]> {
    const response = await apiClient.get<{ conversations: ConversationDto[] }>('/chat/sessions', {
        params,
    })

    return response.data.conversations.map(mapConversationDto)
}

export async function sendChatMessage(
    payload: { conversationId?: string; message: string },
    params?: { scenario?: string },
): Promise<Message> {
    const response = await apiClient.post<ChatResponseDto>('/chat/stream', payload, {
        params,
        timeout: CHAT_REQUEST_TIMEOUT_MS,
    })

    return mapMessageDto(response.data.message)
}
