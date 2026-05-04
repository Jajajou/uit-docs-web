import type { QueryClient } from '@tanstack/react-query'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, useCallback } from 'react'
import { useStream } from '@langchain/langgraph-sdk/react';
import { getConversations, sendChatMessage } from '@/entities/chat/api'
import { langgraphClient } from '@/entities/chat/langgraph'
import type { Message } from '@/entities/chat/types'

const makeUUID = () => {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID()
    }
    return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)
}

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
    const [threadId, setThreadId] = useState(() => makeUUID())

    const handleThreadId = useCallback((id: string) => {
        setThreadId(id)
    }, [])

    const { messages: streamMessages, isLoading, submit } = useStream({
        client: langgraphClient,
        assistantId: params?.assistantId ?? '5bbc8364-e383-5087-8a2f-b6d27677f7a1',
        threadId,
        onThreadId: handleThreadId,
        messagesKey: 'messages',
    })

    const mappedMessages = useMemo((): Message[] => {
        const messages = (streamMessages || []).map((msg: any) => {
            if (!msg) return null;

            let content = ''
            // LangGraph SDK messages often have content as string or MessageContent object
            if (typeof msg.content === 'string') {
                content = msg.content
            } else if (Array.isArray(msg.content)) {
                content = msg.content.map((c: any) => (typeof c === 'string' ? c : c.text || '')).join('')
            } else if (msg.content && typeof msg.content === 'object') {
                content = (msg.content as any).text || JSON.stringify(msg.content)
            }

            // Extract temporal metadata and references from common LangGraph patterns
            const metadata = msg.metadata || msg.additional_kwargs || {}
            const references = metadata.references || []
            const warnings = metadata.warnings || []

            return {
                id: msg.id || makeUUID(),
                role: msg.type === 'human' || msg.role === 'user' ? 'user' : 'assistant',
                content: content || '',
                createdAt: new Date().toISOString(),
                confidence: metadata.confidence ?? 0.8,
                references: (references || []).map((ref: any) => ({
                    id: ref.id || Math.random().toString(36).slice(2),
                    title: ref.title || 'Tài liệu',
                    href: ref.href || ref.url || '#',
                    excerpt: ref.excerpt || '',
                    statusLabel: ref.status_label || 'Hợp lệ',
                })),
                warnings: (warnings || []).map((w: any) => ({
                    code: w.code || 'warning',
                    message: w.message || '',
                })),
            }
        }).filter(Boolean) as Message[]

        return messages
    }, [streamMessages])

    return {
        messages: mappedMessages,
        isLoading,
        sendMessage: (message: string) =>
            submit(
                { messages: [{ role: 'user', content: message }] },
                { threadId }
            ),
    }
}
