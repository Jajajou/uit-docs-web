import { apiClient } from '@/shared/api/client'
import { mapChatResponseDto, mapConversationDto } from '@/entities/chat/mappers'
import type { ChatResponse, ChatResponseDto, Conversation, ConversationDto, PersistLiveChatRequest } from '@/entities/chat/types'

const CHAT_REQUEST_TIMEOUT_MS = 90000

export async function getConversations(params?: { scenario?: string }): Promise<Conversation[]> {
    const response = await apiClient.get<{ conversations: ConversationDto[] }>('/chat/sessions', {
        params,
    })

    return response.data.conversations.map(mapConversationDto)
}

export async function sendChatMessage(
    payload: { conversationId?: string; message: string; signal?: AbortSignal },
    params?: { scenario?: string },
): Promise<ChatResponse> {
    const { signal, ...requestPayload } = payload

    const response = await apiClient.post<ChatResponseDto>('/chat/stream', requestPayload, {
        params,
        timeout: CHAT_REQUEST_TIMEOUT_MS,
        signal,
    })

    return mapChatResponseDto(response.data)
}

export async function persistLiveChatMessage(
    payload: PersistLiveChatRequest,
    params?: { scenario?: string },
): Promise<ChatResponse> {
    const response = await apiClient.post<ChatResponseDto>('/chat/live-sync', payload, {
        params,
        timeout: CHAT_REQUEST_TIMEOUT_MS,
    })

    return mapChatResponseDto(response.data)
}

export async function deleteConversation(conversationId: string, params?: { scenario?: string }): Promise<void> {
    await apiClient.delete(`/chat/sessions/${conversationId}`, {
        params,
    })
}

export async function clearConversations(params?: { scenario?: string }): Promise<void> {
    await apiClient.delete('/chat/sessions', {
        params,
    })
}
