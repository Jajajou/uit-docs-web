import type { QueryClient } from '@tanstack/react-query'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getConversations, sendChatMessage } from '@/entities/chat/api'

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
        mutationFn: (payload: { conversationId?: string; message: string }) => sendChatMessage(payload, params),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['chat', 'conversations'] })
        },
    })
}
