import type { QueryClient } from '@tanstack/react-query'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'
import { useStream } from '@langchain/langgraph-sdk/react'
import { getConversations, sendChatMessage } from '@/entities/chat/api'
import { langgraphClient } from '@/entities/chat/langgraph'
import type { Message } from '@/entities/chat/types'

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

export function useChatStream(params?: { assistantId?: string }) {
    // The current SDK version on disk uses isLoading instead of status in BaseStream
    const { messages: streamMessages, isLoading, submit } = useStream({
        client: langgraphClient,
        assistantId: params?.assistantId ?? 'agent',
    })

    const mappedMessages = useMemo((): Message[] => {
        return (streamMessages || []).map((msg: any) => {
            let content = ''
            if (typeof msg.content === 'string') {
                content = msg.content
            } else if (Array.isArray(msg.content)) {
                content = msg.content.map((c: any) => (typeof c === 'string' ? c : c.text || '')).join('')
            }

            const references = msg.additional_kwargs?.references || msg.metadata?.references || []
            const warnings = msg.additional_kwargs?.warnings || msg.metadata?.warnings || []

            return {
                id: msg.id,
                role: msg.type === 'human' ? 'user' : 'assistant',
                content,
                createdAt: new Date().toISOString(),
                confidence: msg.metadata?.confidence,
                references: references.map((ref: any) => ({
                    id: ref.id || Math.random().toString(36).slice(2),
                    title: ref.title || 'Tài liệu',
                    href: ref.href || ref.url || '#',
                    excerpt: ref.excerpt || '',
                    statusLabel: ref.status_label || 'Hợp lệ',
                })),
                warnings: warnings.map((w: any) => ({
                    code: w.code || 'warning',
                    message: w.message || '',
                })),
            }
        })
    }, [streamMessages])

    return {
        messages: mappedMessages,
        isLoading,
        sendMessage: (message: string) => submit({ messages: [{ role: 'user', content: message }] }),
    }
}
