import { FetchStreamTransport } from '@langchain/langgraph-sdk/react'
import type { Message, PersistLiveChatRequest } from '@/entities/chat/types'

const DEFAULT_LANGGRAPH_API_URL = '/api/langgraph'
const DEFAULT_LANGGRAPH_ASSISTANT_ID = 'retrieval'
const LANGGRAPH_ROOT_RESOURCE_PATHS = ['/assistants', '/runs', '/store', '/threads']

type LangGraphMessageType = 'human' | 'ai' | 'system'

interface LangGraphMessageInput {
    type: LangGraphMessageType
    content: string
}

interface LangGraphMessageLike {
    type?: unknown
    content?: unknown
    kwargs?: { content?: unknown } | null
}

interface LangGraphStreamConfig {
    apiUrl: string
    assistantId: string
    enabled: boolean
    transport?: FetchStreamTransport<Record<string, unknown>>
    fetch?: typeof fetch
    callerOptions?: {
        fetch: typeof fetch
    }
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null
}

function isEnabledFlag(value: unknown) {
    if (typeof value === 'boolean') {
        return value
    }

    return String(value ?? '')
        .trim()
        .toLowerCase() === 'true'
}

function resolveDefaultLangGraphApiUrl(apiBaseUrl: string) {
    const normalizedBaseUrl = apiBaseUrl.trim().replace(/\/+$/, '')

    if (!normalizedBaseUrl) {
        return DEFAULT_LANGGRAPH_API_URL
    }

    if (normalizedBaseUrl.endsWith('/api')) {
        return `${normalizedBaseUrl}/langgraph`
    }

    return `${normalizedBaseUrl}/api/langgraph`
}

export function resolveRuntimeAbsoluteUrl(url: string, origin?: string) {
    const trimmedUrl = url.trim()
    if (!trimmedUrl || !origin) {
        return trimmedUrl
    }

    try {
        return new URL(trimmedUrl, origin).toString()
    } catch {
        return trimmedUrl
    }
}

function isRootLangGraphResourcePath(pathname: string) {
    return LANGGRAPH_ROOT_RESOURCE_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`))
}

export function rewriteLangGraphProxyRequestUrl(requestUrl: string, apiUrl: string, origin?: string) {
    const absoluteApiUrl = resolveRuntimeAbsoluteUrl(apiUrl, origin)
    if (!absoluteApiUrl) {
        return requestUrl
    }

    try {
        const apiBaseUrl = new URL(absoluteApiUrl)
        const targetUrl = new URL(requestUrl, apiBaseUrl.origin)
        const proxyBasePath = apiBaseUrl.pathname.replace(/\/+$/, '')

        if (!proxyBasePath || proxyBasePath === '/' || targetUrl.origin !== apiBaseUrl.origin) {
            return targetUrl.toString()
        }

        const isAlreadyPrefixed =
            targetUrl.pathname === proxyBasePath || targetUrl.pathname.startsWith(`${proxyBasePath}/`)

        if (!isRootLangGraphResourcePath(targetUrl.pathname) || isAlreadyPrefixed) {
            return targetUrl.toString()
        }

        const rewrittenUrl = new URL(`${proxyBasePath}${targetUrl.pathname}`, apiBaseUrl.origin)
        rewrittenUrl.search = targetUrl.search
        rewrittenUrl.hash = targetUrl.hash
        return rewrittenUrl.toString()
    } catch {
        return requestUrl
    }
}

function createLangGraphProxyFetch(apiUrl: string, origin?: string) {
    return async (input: RequestInfo | URL, init?: RequestInit) => {
        const requestUrl =
            typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
        const rewrittenUrl = rewriteLangGraphProxyRequestUrl(requestUrl, apiUrl, origin)

        if (input instanceof Request) {
            if (init) {
                return fetch(rewrittenUrl, init)
            }

            return fetch(new Request(rewrittenUrl, input))
        }

        return fetch(rewrittenUrl, init)
    }
}

function resolveLangGraphRunStreamUrl(apiUrl: string, origin?: string) {
    if (!origin) {
        return `${apiUrl.replace(/\/+$/, '')}/runs/stream`
    }

    return rewriteLangGraphProxyRequestUrl('/runs/stream', apiUrl, origin)
}

function createLangGraphStreamTransport(apiUrl: string, assistantId: string, origin?: string) {
    const streamApiUrl = resolveLangGraphRunStreamUrl(apiUrl, origin)

    return new FetchStreamTransport<Record<string, unknown>>({
        apiUrl: streamApiUrl,
        onRequest: (_url, init) => {
            let parsedBody: Record<string, unknown> = {}
            if (typeof init.body === 'string' && init.body.trim()) {
                try {
                    parsedBody = JSON.parse(init.body) as Record<string, unknown>
                } catch {
                    parsedBody = {}
                }
            }

            const headers = new Headers(init.headers)
            headers.set('Accept', 'text/event-stream')
            headers.set('Content-Type', 'application/json')

            return {
                ...init,
                headers,
                body: JSON.stringify({
                    assistant_id: assistantId,
                    input: parsedBody.input ?? null,
                    context: parsedBody.context,
                    command: parsedBody.command,
                    config: parsedBody.config,
                    stream_mode: ['values', 'messages'],
                    stream_resumable: false,
                    on_disconnect: 'cancel',
                }),
            }
        },
    })
}

function normalizeMessageType(role: Message['role']): LangGraphMessageType {
    if (role === 'user') {
        return 'human'
    }

    if (role === 'assistant') {
        return 'ai'
    }

    return 'system'
}

function pushTextPart(parts: string[], value: unknown) {
    if (typeof value === 'string') {
        const text = value.trim()
        if (text) {
            parts.push(text)
        }
        return
    }

    if (Array.isArray(value)) {
        for (const item of value) {
            pushTextPart(parts, item)
        }
        return
    }

    if (!isRecord(value)) {
        return
    }

    const type = typeof value.type === 'string' ? value.type.toLowerCase() : ''
    if (type === 'text') {
        pushTextPart(parts, value.text ?? value.content ?? value.value)
        return
    }

    pushTextPart(parts, value.text ?? value.content ?? value.value)
}

export function extractLangGraphText(value: unknown): string {
    const parts: string[] = []
    pushTextPart(parts, value)
    return parts.join('\n').trim()
}

export function resolveLangGraphStreamConfig(env: {
    VITE_API_BASE_URL?: unknown
    VITE_LANGGRAPH_API_URL?: unknown
    VITE_LANGGRAPH_ASSISTANT_ID?: unknown
    VITE_ENABLE_MOCKS?: unknown
    VITEST?: unknown
}): LangGraphStreamConfig {
    const configuredApiBaseUrl = String(env.VITE_API_BASE_URL ?? '').trim()
    const apiUrl =
        String(env.VITE_LANGGRAPH_API_URL ?? '').trim() || resolveDefaultLangGraphApiUrl(configuredApiBaseUrl)
    const assistantId = String(env.VITE_LANGGRAPH_ASSISTANT_ID ?? DEFAULT_LANGGRAPH_ASSISTANT_ID).trim() || DEFAULT_LANGGRAPH_ASSISTANT_ID
    const enabled = Boolean(assistantId) && !isEnabledFlag(env.VITE_ENABLE_MOCKS) && !isEnabledFlag(env.VITEST)

    return {
        apiUrl,
        assistantId,
        enabled,
    }
}

export function getLangGraphStreamConfig() {
    const config = resolveLangGraphStreamConfig(import.meta.env as Record<string, unknown>)
    const origin = typeof window === 'undefined' ? undefined : window.location.origin
    const apiUrl = resolveRuntimeAbsoluteUrl(config.apiUrl, origin)
    const transport = createLangGraphStreamTransport(apiUrl, config.assistantId, origin)

    if (!origin) {
        return {
            ...config,
            apiUrl,
            transport,
        }
    }

    const proxyFetch = createLangGraphProxyFetch(apiUrl, origin)

    return {
        ...config,
        apiUrl,
        transport,
        fetch: proxyFetch,
        callerOptions: {
            fetch: proxyFetch,
        },
    }
}

export function buildLangGraphSubmissionMessages(history: Message[], message: string): LangGraphMessageInput[] {
    const trimmedMessage = message.trim()
    const historyMessages = history.flatMap((item) => {
        const content = item.content.trim()
        if (!content) {
            return []
        }

        return [
            {
                type: normalizeMessageType(item.role),
                content,
            },
        ]
    })

    return trimmedMessage
        ? [...historyMessages, { type: 'human', content: trimmedMessage }]
        : historyMessages
}

export function getLatestAssistantStreamText(messages: unknown[], values: unknown): string {
    const reversedMessages = [...messages].reverse()

    for (const message of reversedMessages) {
        if (!isRecord(message)) {
            continue
        }

        const messageLike = message as LangGraphMessageLike
        const rawType = typeof messageLike.type === 'string' ? messageLike.type.toLowerCase() : ''
        if (!['ai', 'assistant'].includes(rawType)) {
            continue
        }

        const directContent = extractLangGraphText(messageLike.content)
        if (directContent) {
            return directContent
        }

        const kwargsContent = extractLangGraphText(messageLike.kwargs?.content)
        if (kwargsContent) {
            return kwargsContent
        }
    }

    if (!isRecord(values)) {
        return ''
    }

    for (const key of ['final_answer', 'generated_response', 'response_text', 'response']) {
        const text = extractLangGraphText(values[key])
        if (text) {
            return text
        }
    }

    return ''
}

export function buildPersistLiveChatPayload({
    conversationId,
    message,
    messages,
    values,
}: {
    conversationId?: string
    message: string
    messages: unknown[]
    values: unknown
}): PersistLiveChatRequest {
    const resultRecord = isRecord(values) ? { ...values } : {}
    const content = getLatestAssistantStreamText(messages, values)

    if (content && typeof resultRecord.final_answer !== 'string' && typeof resultRecord.generated_response !== 'string') {
        resultRecord.final_answer = content
    }

    if (!Array.isArray(resultRecord.messages)) {
        resultRecord.messages = messages
    }

    return {
        conversationId,
        message,
        result: resultRecord,
    }
}
