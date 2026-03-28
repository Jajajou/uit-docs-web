import { apiClient } from '@/shared/api/client'
import { mapConversationDto, mapMessageDto } from '@/entities/chat/mappers'
import type { ChatResponseDto, Conversation, ConversationDto, Message } from '@/entities/chat/types'

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
    })

    return mapMessageDto(response.data.message)
}
