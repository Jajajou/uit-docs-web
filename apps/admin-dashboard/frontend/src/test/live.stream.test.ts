import { describe, expect, it } from 'vitest'
import {
    buildLangGraphSubmissionMessages,
    buildPersistLiveChatPayload,
    getLatestAssistantStreamText,
    rewriteLangGraphProxyRequestUrl,
    resolveRuntimeAbsoluteUrl,
    resolveLangGraphStreamConfig,
} from '@/entities/chat/live'
import type { Message } from '@/entities/chat/types'

const sampleHistory: Message[] = [
    {
        id: 'msg-user-001',
        role: 'user',
        content: 'Hoc phi hoc ky nay nhu the nao?',
        createdAt: '2026-05-05T10:00:00Z',
        references: [],
        warnings: [],
    },
    {
        id: 'msg-assistant-001',
        role: 'assistant',
        content: 'Thong tin dang duoc doi chieu.',
        createdAt: '2026-05-05T10:00:05Z',
        references: [],
        warnings: [],
    },
]

describe('LangGraph live chat helpers', () => {
    it('maps chat history into LangGraph message input', () => {
        expect(buildLangGraphSubmissionMessages(sampleHistory, 'Lich dang ky mon hoc bat dau khi nao?')).toEqual([
            { type: 'human', content: 'Hoc phi hoc ky nay nhu the nao?' },
            { type: 'ai', content: 'Thong tin dang duoc doi chieu.' },
            { type: 'human', content: 'Lich dang ky mon hoc bat dau khi nao?' },
        ])
    })

    it('extracts assistant text from streamed messages before final values settle', () => {
        const streamedMessages = [
            { type: 'human', content: 'Hoi lich dang ky' },
            {
                type: 'ai',
                content: [
                    {
                        type: 'text',
                        text: 'Thong bao lich dang ky mon hoc da duoc cong bo.',
                    },
                ],
            },
        ]

        expect(getLatestAssistantStreamText(streamedMessages, {})).toBe('Thong bao lich dang ky mon hoc da duoc cong bo.')
    })

    it('builds a sync payload that preserves streamed values and fallback answer text', () => {
        const payload = buildPersistLiveChatPayload({
            conversationId: 'conv-live-001',
            message: 'Lich dang ky mon hoc bat dau khi nao?',
            messages: [
                { type: 'human', content: 'Hoi lich dang ky' },
                { type: 'ai', content: 'Thong bao lich dang ky mon hoc da duoc cong bo.' },
            ],
            values: {
                response_type: 'partial_answer',
                references: [
                    {
                        reference_id: 'ref-001',
                        file_source: 'admin-dashboard-public://doc-004',
                    },
                ],
            },
        })

        expect(payload).toMatchObject({
            conversationId: 'conv-live-001',
            message: 'Lich dang ky mon hoc bat dau khi nao?',
        })
        expect(payload.result.final_answer).toBe('Thong bao lich dang ky mon hoc da duoc cong bo.')
        expect(payload.result.response_type).toBe('partial_answer')
        expect(payload.result.messages).toHaveLength(2)
    })

    it('enables live stream with the backend proxy fallback when mocks are off', () => {
        expect(
            resolveLangGraphStreamConfig({
                VITE_ENABLE_MOCKS: 'false',
            }),
        ).toEqual({
            apiUrl: '/api/langgraph',
            assistantId: 'retrieval',
            enabled: true,
        })
    })

    it('derives the LangGraph endpoint from an absolute API base URL', () => {
        expect(
            resolveLangGraphStreamConfig({
                VITE_ENABLE_MOCKS: 'false',
                VITE_API_BASE_URL: 'http://127.0.0.1:8011/api',
            }),
        ).toEqual({
            apiUrl: 'http://127.0.0.1:8011/api/langgraph',
            assistantId: 'retrieval',
            enabled: true,
        })
    })

    it('converts relative LangGraph paths into absolute browser URLs when an origin is available', () => {
        expect(resolveRuntimeAbsoluteUrl('/api/langgraph', 'http://127.0.0.1:3000')).toBe(
            'http://127.0.0.1:3000/api/langgraph',
        )
    })

    it('rewrites SDK root requests back through the LangGraph proxy prefix', () => {
        expect(
            rewriteLangGraphProxyRequestUrl(
                'http://127.0.0.1:3000/threads/thread-123/stream/events',
                'http://127.0.0.1:3000/api/langgraph',
            ),
        ).toBe('http://127.0.0.1:3000/api/langgraph/threads/thread-123/stream/events')
    })

    it('does not rewrite requests that are already under the proxy prefix', () => {
        expect(
            rewriteLangGraphProxyRequestUrl(
                'http://127.0.0.1:3000/api/langgraph/runs/stream',
                'http://127.0.0.1:3000/api/langgraph',
            ),
        ).toBe('http://127.0.0.1:3000/api/langgraph/runs/stream')
    })

    it('disables live stream while browser mocks are enabled', () => {
        expect(
            resolveLangGraphStreamConfig({
                VITE_ENABLE_MOCKS: 'true',
                VITE_LANGGRAPH_API_URL: 'https://example.com',
                VITE_LANGGRAPH_ASSISTANT_ID: 'retrieval',
            }),
        ).toMatchObject({
            enabled: false,
        })
    })
})
