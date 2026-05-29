import type { QueryClient } from '@tanstack/react-query'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clearConversations, deleteConversation, getConversations, persistLiveChatMessage, sendChatMessage } from '@/entities/chat/api'
import type { PersistLiveChatRequest } from '@/entities/chat/types'

export function getConversationsQueryOptions(params?: { scenario?: string }) {
    return {
        queryKey: ['chat', 'conversations', params?.scenario ?? 'happy'],
        queryFn: () => getConversations(params),
    }
}

export function useConversationsQuery(params?: { scenario?: string }) {
    return useQuery(getConversationsQueryOptions(params))
}

export function prefetchConversationsQuery(queryClient: QueryClient, params?: { scenario?: string }) {
    return queryClient.prefetchQuery(getConversationsQueryOptions(params))
}

export function useSendChatMessageMutation(params?: { scenario?: string }) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (payload: { conversationId?: string; message: string; signal?: AbortSignal }) => sendChatMessage(payload, params),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['chat', 'conversations'] })
        },
    })
}

export function usePersistLiveChatMessageMutation(params?: { scenario?: string }) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (payload: PersistLiveChatRequest) => persistLiveChatMessage(payload, params),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['chat', 'conversations'] })
        },
    })
}

export function useDeleteConversationMutation(params?: { scenario?: string }) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (conversationId: string) => deleteConversation(conversationId, params),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['chat', 'conversations'] })
        },
    })
}

export function useClearConversationsMutation(params?: { scenario?: string }) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: () => clearConversations(params),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['chat', 'conversations'] })
        },
    })
}
