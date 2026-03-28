import { startTransition, useDeferredValue, useEffect, useMemo, useState } from 'react'
import { BookOpenText, MessageSquare, Search, Send, ShieldAlert, Sparkles } from 'lucide-react'
import { RouteIntentLink } from '@/app/router/RouteIntentLink'
import { useConversationsQuery, useSendChatMessageMutation } from '@/entities/chat/queries'
import type { Message } from '@/entities/chat/types'
import { formatDateTime, formatPercent } from '@/shared/lib/format'
import { Badge, Button, Card, EmptyState, Input, Textarea } from '@/shared/ui'

const quickPrompts = [
    'Hoc phi hoc ky nay duoc tinh nhu the nao?',
    'Lich dang ky mon hoc cua khoa 2024 co thay doi khong?',
    'Tai lieu nao dang het hieu luc nhung van bi trich dan?',
]

function getConfidenceTone(confidence?: number) {
    if (typeof confidence !== 'number') {
        return 'neutral' as const
    }

    if (confidence >= 0.8) {
        return 'success' as const
    }

    if (confidence >= 0.55) {
        return 'brand' as const
    }

    return 'warning' as const
}

export function ChatWorkspace({ scenario }: { scenario?: string }) {
    const conversationsQuery = useConversationsQuery({ scenario })
    const sendMessageMutation = useSendChatMessageMutation({ scenario })
    const [selectedConversationId, setSelectedConversationId] = useState('conv-001')
    const [draft, setDraft] = useState('')
    const [conversationSearch, setConversationSearch] = useState('')
    const [localMessagesByConversation, setLocalMessagesByConversation] = useState<Record<string, Message[]>>({})
    const deferredConversationSearch = useDeferredValue(conversationSearch)

    useEffect(() => {
        if (!conversationsQuery.data?.length) {
            return
        }

        if (!conversationsQuery.data.some((conversation) => conversation.id === selectedConversationId)) {
            setSelectedConversationId(conversationsQuery.data[0].id)
        }
    }, [conversationsQuery.data, selectedConversationId])

    const filteredConversations = useMemo(() => {
        if (!conversationsQuery.data) {
            return []
        }

        const normalizedSearch = deferredConversationSearch.trim().toLowerCase()

        if (!normalizedSearch) {
            return conversationsQuery.data
        }

        return conversationsQuery.data.filter((conversation) => {
            const titleMatches = conversation.title.toLowerCase().includes(normalizedSearch)
            const contentMatches = conversation.messages.some((message) => message.content.toLowerCase().includes(normalizedSearch))

            return titleMatches || contentMatches
        })
    }, [conversationsQuery.data, deferredConversationSearch])

    const selectedConversation = useMemo(
        () => conversationsQuery.data?.find((conversation) => conversation.id === selectedConversationId) ?? filteredConversations[0],
        [conversationsQuery.data, filteredConversations, selectedConversationId],
    )

    const combinedMessages = useMemo(
        () => [
            ...(selectedConversation?.messages ?? []),
            ...(!selectedConversation ? [] : localMessagesByConversation[selectedConversation.id] ?? []),
        ],
        [localMessagesByConversation, selectedConversation],
    )
    const latestAssistantMessage = useMemo(
        () => [...combinedMessages].reverse().find((message) => message.role === 'assistant'),
        [combinedMessages],
    )
    const assistantMessages = combinedMessages.filter((message) => message.role === 'assistant')
    const averageConfidence = assistantMessages.length
        ? assistantMessages.reduce((sum, message) => sum + (message.confidence ?? 0), 0) / assistantMessages.length
        : undefined
    const totalReferences = combinedMessages.reduce((sum, message) => sum + message.references.length, 0)
    const totalWarnings = combinedMessages.reduce((sum, message) => sum + message.warnings.length, 0)

    const sendDraftMessage = async () => {
        if (!draft.trim() || !selectedConversation) {
            return
        }

        const message = draft.trim()
        const conversationId = selectedConversation.id
        const localUserMessage: Message = {
            id: `local-user-${crypto.randomUUID()}`,
            role: 'user',
            content: message,
            createdAt: new Date().toISOString(),
            references: [],
            warnings: [],
        }

        startTransition(() => {
            setLocalMessagesByConversation((current) => ({
                ...current,
                [conversationId]: [...(current[conversationId] ?? []), localUserMessage],
            }))
        })
        setDraft('')

        try {
            const assistantMessage = await sendMessageMutation.mutateAsync({ conversationId, message })
            startTransition(() => {
                setLocalMessagesByConversation((current) => ({
                    ...current,
                    [conversationId]: [...(current[conversationId] ?? []), assistantMessage],
                }))
            })
        } catch {
            // Mutation error is already surfaced through the existing mutation state.
        }
    }

    if (conversationsQuery.isLoading) {
        return <Card className="h-[36rem] animate-pulse" />
    }

    if (conversationsQuery.isError) {
        return <Card className="text-sm text-error-700 dark:text-error-300">{conversationsQuery.error.message}</Card>
    }

    if (!conversationsQuery.data || conversationsQuery.data.length === 0) {
        return (
            <EmptyState
                icon={MessageSquare}
                title="No conversations yet"
                description="Use this workspace to validate citations, warnings and confidence rendering before backend integration."
            />
        )
    }

    return (
        <div className="grid gap-6 2xl:grid-cols-[18rem_minmax(0,1fr)_22rem]">
            <Card className="space-y-4">
                <div className="space-y-1">
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">Conversation index</div>
                    <p className="text-sm text-gray-500">Use search to validate how the shell behaves when users jump between student questions.</p>
                </div>

                <Input
                    label="Search conversations"
                    value={conversationSearch}
                    onChange={(event) => setConversationSearch(event.target.value)}
                    placeholder="Hoc phi, hoc bong, dang ky mon hoc..."
                />

                <div className="flex flex-wrap gap-2">
                    <Badge tone="neutral">{filteredConversations.length} threads</Badge>
                    <Badge tone={totalWarnings > 0 ? 'warning' : 'success'}>{totalWarnings} warnings</Badge>
                    <Badge tone={totalReferences > 0 ? 'brand' : 'neutral'}>{totalReferences} references</Badge>
                </div>

                <div className="space-y-2">
                    {filteredConversations.length === 0 ? (
                        <div className="rounded-2xl border border-dashed border-gray-200 px-4 py-6 text-sm text-gray-500 dark:border-gray-800">
                            No threads match the current search.
                        </div>
                    ) : (
                        filteredConversations.map((conversation) => {
                            const isSelected = selectedConversation?.id === conversation.id
                            const warningCount = conversation.messages.reduce((sum, message) => sum + message.warnings.length, 0)
                            const referenceCount = conversation.messages.reduce((sum, message) => sum + message.references.length, 0)

                            return (
                                <button
                                    key={conversation.id}
                                    type="button"
                                    onClick={() =>
                                        startTransition(() => {
                                            setSelectedConversationId(conversation.id)
                                        })
                                    }
                                    className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                                        isSelected
                                            ? 'border-brand-300 bg-brand-50 dark:border-brand-800 dark:bg-brand-950'
                                            : 'border-gray-200 bg-white hover:bg-gray-50 dark:border-gray-800 dark:bg-gray-950 dark:hover:bg-gray-900'
                                    }`}
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <div>
                                            <div className="font-medium text-gray-900 dark:text-white">{conversation.title}</div>
                                            <div className="mt-1 text-xs text-gray-500">{formatDateTime(conversation.updatedAt)}</div>
                                        </div>
                                        <div className="flex flex-col items-end gap-2">
                                            <Badge tone={warningCount > 0 ? 'warning' : 'success'}>{warningCount} alerts</Badge>
                                            <span className="text-xs text-gray-500">{referenceCount} refs</span>
                                        </div>
                                    </div>
                                </button>
                            )
                        })
                    )}
                </div>
            </Card>

            <div className="space-y-4">
                <Card className="space-y-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="space-y-1">
                            <div className="flex items-center gap-2">
                                <Badge tone="brand">Public answer layer</Badge>
                                <Badge tone={getConfidenceTone(averageConfidence)}>
                                    Avg confidence {typeof averageConfidence === 'number' ? formatPercent(averageConfidence) : 'N/A'}
                                </Badge>
                            </div>
                            <div className="text-xl font-semibold text-gray-950 dark:text-white">{selectedConversation?.title}</div>
                            <p className="text-sm text-gray-500">
                                Students should always see the answer together with citations, freshness warnings and confidence cues.
                            </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            {quickPrompts.slice(0, 2).map((prompt) => (
                                <Button
                                    key={prompt}
                                    type="button"
                                    variant="secondary"
                                    size="sm"
                                    onClick={() => setDraft(prompt)}
                                >
                                    <Sparkles size={14} />
                                    {prompt}
                                </Button>
                            ))}
                        </div>
                    </div>

                    <div className="grid gap-3 md:grid-cols-3">
                        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950">
                            <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Messages</div>
                            <div className="mt-2 text-2xl font-bold text-gray-950 dark:text-white">{combinedMessages.length}</div>
                        </div>
                        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950">
                            <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Referenced sources</div>
                            <div className="mt-2 text-2xl font-bold text-gray-950 dark:text-white">{totalReferences}</div>
                        </div>
                        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950">
                            <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Warnings</div>
                            <div className="mt-2 text-2xl font-bold text-gray-950 dark:text-white">{totalWarnings}</div>
                        </div>
                    </div>
                </Card>

                <Card className="space-y-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                        <BookOpenText size={16} />
                        Conversation transcript
                    </div>

                    <div className="max-h-[38rem] space-y-4 overflow-y-auto pr-1">
                        {combinedMessages.map((message) => (
                            <div
                                key={message.id}
                                className={`rounded-2xl px-4 py-3 ${
                                    message.role === 'user'
                                        ? 'bg-gray-100 dark:bg-gray-800'
                                        : message.role === 'system'
                                          ? 'border border-warning-200 bg-warning-50 dark:border-warning-800 dark:bg-warning-950'
                                          : 'border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950'
                                }`}
                            >
                                <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">{message.role}</span>
                                        <span className="text-xs text-gray-500">{formatDateTime(message.createdAt)}</span>
                                    </div>
                                    {typeof message.confidence === 'number' ? (
                                        <Badge tone={getConfidenceTone(message.confidence)}>Confidence {formatPercent(message.confidence)}</Badge>
                                    ) : null}
                                </div>
                                <p className="text-sm leading-6 text-gray-700 dark:text-gray-200">{message.content}</p>

                                {message.references.length > 0 ? (
                                    <div className="mt-4 space-y-2 rounded-xl bg-gray-50 p-3 dark:bg-gray-900">
                                        <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">References</div>
                                        {message.references.map((reference) => (
                                            <div key={reference.id} className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-950">
                                                <div className="flex items-start justify-between gap-3">
                                                    <div className="space-y-1">
                                                        <RouteIntentLink
                                                            to={reference.href}
                                                            className="text-sm font-medium text-gray-900 hover:text-brand-700 dark:text-white dark:hover:text-brand-200"
                                                        >
                                                            {reference.title}
                                                        </RouteIntentLink>
                                                        <div className="text-xs text-gray-500">{reference.statusLabel}</div>
                                                    </div>
                                                    <Badge tone={reference.statusLabel.toLowerCase().includes('archive') ? 'warning' : 'brand'}>Source</Badge>
                                                </div>
                                                <div className="mt-2 text-xs text-gray-500">{reference.excerpt}</div>
                                            </div>
                                        ))}
                                    </div>
                                ) : null}

                                {message.warnings.length > 0 ? (
                                    <div className="mt-3 space-y-2">
                                        {message.warnings.map((warning) => (
                                            <div
                                                key={warning.code}
                                                className="rounded-xl border border-warning-200 bg-warning-50 px-3 py-2 text-xs text-warning-800 dark:border-warning-800 dark:bg-warning-950 dark:text-warning-200"
                                            >
                                                {warning.message}
                                            </div>
                                        ))}
                                    </div>
                                ) : null}
                            </div>
                        ))}
                    </div>
                </Card>

                <Card className="space-y-4">
                    <div className="flex flex-wrap gap-2">
                        {quickPrompts.map((prompt) => (
                            <Button key={prompt} type="button" variant="ghost" size="sm" onClick={() => setDraft(prompt)}>
                                <Search size={14} />
                                {prompt}
                            </Button>
                        ))}
                    </div>

                    <Textarea
                        label="Mock message"
                        value={draft}
                        onChange={(event) => setDraft(event.target.value)}
                        onKeyDown={(event) => {
                            if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                                event.preventDefault()
                                void sendDraftMessage()
                            }
                        }}
                        placeholder="Ask a question to validate chat states..."
                    />
                    <div className="flex justify-end">
                        {sendMessageMutation.isError ? (
                            <div className="mr-auto rounded-xl border border-error-200 bg-error-50 px-3 py-2 text-xs text-error-700 dark:border-error-800 dark:bg-error-950 dark:text-error-300">
                                {sendMessageMutation.error.message}
                            </div>
                        ) : null}
                        <Button
                            isLoading={sendMessageMutation.isPending}
                            disabled={!draft.trim() || !selectedConversation}
                            onClick={() => {
                                void sendDraftMessage()
                            }}
                        >
                            <Send size={16} />
                            Send mock message
                        </Button>
                    </div>
                </Card>
            </div>

            <div className="space-y-4">
                <Card className="space-y-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                        <ShieldAlert size={16} />
                        Latest answer health
                    </div>

                    {latestAssistantMessage ? (
                        <div className="space-y-3">
                            <div className="flex flex-wrap gap-2">
                                <Badge tone={getConfidenceTone(latestAssistantMessage.confidence)}>
                                    Confidence{' '}
                                    {typeof latestAssistantMessage.confidence === 'number'
                                        ? formatPercent(latestAssistantMessage.confidence)
                                        : 'N/A'}
                                </Badge>
                                <Badge tone={latestAssistantMessage.warnings.length > 0 ? 'warning' : 'success'}>
                                    {latestAssistantMessage.warnings.length} warnings
                                </Badge>
                                <Badge tone={latestAssistantMessage.references.length > 0 ? 'brand' : 'neutral'}>
                                    {latestAssistantMessage.references.length} references
                                </Badge>
                            </div>
                            <p className="text-sm text-gray-500">
                                Assistant answers should stay grounded in approved or reviewable documents, not just free-form generation.
                            </p>
                        </div>
                    ) : (
                        <p className="text-sm text-gray-500">No assistant answer selected yet.</p>
                    )}
                </Card>

                <Card className="space-y-4">
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">Reference stack</div>
                    {latestAssistantMessage?.references.length ? (
                        <div className="space-y-3">
                            {latestAssistantMessage.references.map((reference) => (
                                <div key={reference.id} className="rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950">
                                    <RouteIntentLink
                                        to={reference.href}
                                        className="text-sm font-semibold text-gray-900 hover:text-brand-700 dark:text-white dark:hover:text-brand-200"
                                    >
                                        {reference.title}
                                    </RouteIntentLink>
                                    <div className="mt-1 text-xs text-gray-500">{reference.statusLabel}</div>
                                    <div className="mt-2 text-sm text-gray-600 dark:text-gray-300">{reference.excerpt}</div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-gray-500">Selected conversation does not expose references yet.</p>
                    )}
                </Card>

                <Card className="space-y-4">
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">Warning contract</div>
                    {latestAssistantMessage?.warnings.length ? (
                        <div className="space-y-2">
                            {latestAssistantMessage.warnings.map((warning) => (
                                <div
                                    key={warning.code}
                                    className="rounded-xl border border-warning-200 bg-warning-50 px-3 py-2 text-sm text-warning-800 dark:border-warning-800 dark:bg-warning-950 dark:text-warning-200"
                                >
                                    <div className="font-medium">{warning.code}</div>
                                    <div className="mt-1 text-xs">{warning.message}</div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-gray-500">No active warnings on the latest assistant answer.</p>
                    )}

                    <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 text-sm text-gray-500 dark:border-gray-800 dark:bg-gray-950">
                        Public chat should always surface uncertainty. Low-confidence, archived or pending-review sources must never look like final truth.
                    </div>
                </Card>
            </div>
        </div>
    )
}
