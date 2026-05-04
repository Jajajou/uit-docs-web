import { startTransition, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
    BookOpenText,
    CalendarDays,
    ChevronLeft,
    ChevronRight,
    GraduationCap,
    History,
    Loader2,
    Search,
    Send,
    Sparkles,
} from 'lucide-react'
import { RouteIntentLink } from '@/app/router/RouteIntentLink'
import { useChatStream, useConversationsQuery, useSendChatMessageMutation } from '@/entities/chat/queries'
import type { Message } from '@/entities/chat/types'
import { cn } from '@/shared/lib/cn'
import { formatDateTime, formatPercent } from '@/shared/lib/format'
import { Badge, Button, Card, Input } from '@/shared/ui'

const quickPrompts = [
    { label: 'Học phí học kỳ này được tính như thế nào?', icon: GraduationCap },
    { label: 'Lịch đăng ký môn học của khóa 2024 có thay đổi không?', icon: CalendarDays },
    { label: 'Điều kiện học bổng hiện tại là gì?', icon: BookOpenText },
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

function getReferenceStatusMeta(statusLabel: string) {
    const lower = statusLabel.toLowerCase()

    if (lower.includes('approve') || lower.includes('valid')) {
        return {
            tone: 'success' as const,
            label: 'Còn hiệu lực',
            cardClassName: 'border-success-200 bg-success-50/80 dark:border-success-900 dark:bg-success-950/25',
        }
    }

    if (lower.includes('pending') || lower.includes('review')) {
        return {
            tone: 'warning' as const,
            label: 'Chờ rà soát',
            cardClassName: 'border-warning-200 bg-warning-50/80 dark:border-warning-900 dark:bg-warning-950/25',
        }
    }

    if (lower.includes('archive') || lower.includes('superseded') || lower.includes('expired')) {
        return {
            tone: 'neutral' as const,
            label: 'Đã thay thế',
            cardClassName: 'border-gray-200 bg-gray-50/90 dark:border-gray-800 dark:bg-gray-900/90 opacity-85',
        }
    }

    return {
        tone: 'brand' as const,
        label: statusLabel,
        cardClassName: 'border-brand-200 bg-brand-50/80 dark:border-brand-800 dark:bg-brand-950/25',
    }
}

type ChatCanvasMode = 'fresh' | 'history'

function AssistantMessage({ message, onOpenSources }: { message: Message; onOpenSources: (messageId: string) => void }) {
    return (
        <div className="flex gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-600 text-white shadow-theme-sm">
                <Sparkles size={18} />
            </div>
            <div className="min-w-0 flex-1 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-semibold text-gray-950 dark:text-white">UIT AI</div>
                    <Badge tone={getConfidenceTone(message.confidence)}>
                        {typeof message.confidence === 'number' ? `Độ tin cậy ${formatPercent(message.confidence)}` : 'Trả lời tham chiếu'}
                    </Badge>
                    {message.warnings.length > 0 ? <Badge tone="warning">{message.warnings.length} cảnh báo</Badge> : null}
                </div>

                <div className="rounded-[1.75rem] border border-white/70 bg-white/90 px-5 py-4 text-[15px] leading-7 text-gray-700 shadow-theme-sm dark:border-white/8 dark:bg-[#1a2538]/90 dark:text-gray-100">
                    {message.content}
                </div>

                {message.references.length > 0 ? (
                    <div className="flex flex-wrap items-center gap-2">
                        <Button variant="outline" size="sm" onClick={() => onOpenSources(message.id)}>
                            <BookOpenText size={16} />
                            Nguồn tài liệu
                        </Button>
                        {message.references.slice(0, 2).map((reference) => (
                            <Badge key={reference.id} tone="neutral">
                                {reference.title}
                            </Badge>
                        ))}
                    </div>
                ) : null}
            </div>
        </div>
    )
}

function UserMessage({ message }: { message: Message }) {
    return (
        <div className="flex justify-end">
            <div className="max-w-[44rem] rounded-[1.75rem] border border-brand-100 bg-brand-50/90 px-5 py-4 text-[15px] leading-7 text-gray-800 shadow-theme-xs dark:border-brand-900 dark:bg-brand-950/40 dark:text-brand-50">
                {message.content}
            </div>
        </div>
    )
}

function TypingIndicator() {
    return (
        <div className="flex gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-600 text-white shadow-theme-sm">
                <Loader2 size={18} className="animate-spin" />
            </div>
            <div className="rounded-[1.75rem] border border-white/70 bg-white/90 px-5 py-4 text-sm text-gray-500 shadow-theme-sm dark:border-white/8 dark:bg-[#1a2538]/90 dark:text-gray-300">
                UIT AI đang tổng hợp câu trả lời từ nguồn tài liệu...
            </div>
        </div>
    )
}

export function ChatWorkspace({ scenario }: { scenario?: string }) {
    const conversationsQuery = useConversationsQuery({ scenario })
    const sendMessageMutation = useSendChatMessageMutation({ scenario })
    const streamChat = useChatStream({ assistantId: 'agent' })
    const [selectedConversationId, setSelectedConversationId] = useState('conv-001')
    const [canvasMode, setCanvasMode] = useState<ChatCanvasMode>('fresh')
    const [draft, setDraft] = useState('')
    const [conversationSearch, setConversationSearch] = useState('')
    const [localMessagesByConversation, setLocalMessagesByConversation] = useState<Record<string, Message[]>>({})
    const [freshMessages, setFreshMessages] = useState<Message[]>([])
    const [isHistoryOpen, setIsHistoryOpen] = useState(false)
    const [isReferencePanelOpen, setIsReferencePanelOpen] = useState(false)
    const [activeReferenceMessageId, setActiveReferenceMessageId] = useState<string | null>(null)
    const deferredConversationSearch = useDeferredValue(conversationSearch)
    const messageEndRef = useRef<HTMLDivElement | null>(null)

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

    const historyMessages = useMemo(
        () => [
            ...(selectedConversation?.messages ?? []),
            ...(!selectedConversation ? [] : localMessagesByConversation[selectedConversation.id] ?? []),
        ],
        [localMessagesByConversation, selectedConversation],
    )

    const displayedMessages = canvasMode === 'fresh' ? (streamChat.messages.length > 0 ? streamChat.messages : freshMessages) : historyMessages

    const latestAssistantMessage = useMemo(
        () => [...displayedMessages].reverse().find((message) => message.role === 'assistant'),
        [displayedMessages],
    )

    useEffect(() => {
        if (latestAssistantMessage?.references.length) {
            setActiveReferenceMessageId(latestAssistantMessage.id)
        }
    }, [latestAssistantMessage])

    useEffect(() => {
        messageEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    }, [displayedMessages, sendMessageMutation.isPending, streamChat.isLoading])

    const activeReferenceMessage = useMemo(() => {
        if (!activeReferenceMessageId) {
            return latestAssistantMessage ?? null
        }

        return displayedMessages.find((message) => message.id === activeReferenceMessageId && message.role === 'assistant') ?? latestAssistantMessage ?? null
    }, [activeReferenceMessageId, displayedMessages, latestAssistantMessage])

    const showWelcomeCanvas = canvasMode === 'fresh' && displayedMessages.length === 0
    const activeReferenceCount = activeReferenceMessage?.references.length ?? 0

    const startFreshChat = () => {
        setCanvasMode('fresh')
        setFreshMessages([])
        setDraft('')
        setActiveReferenceMessageId(null)
        setIsReferencePanelOpen(false)
    }

    const openHistoryConversation = (conversationId: string) => {
        startTransition(() => {
            setSelectedConversationId(conversationId)
            setCanvasMode('history')
            setIsHistoryOpen(false)
        })
    }

    const sendDraftMessage = async () => {
        if (!draft.trim()) {
            return
        }

        const message = draft.trim()
        setDraft('')
        
        if (canvasMode === 'fresh') {
            try {
                await streamChat.sendMessage(message)
            } catch (err) {
                console.error('LangGraph stream error:', err)
            }
            return
        }

        const localUserMessage: Message = {
            id: `local-user-${crypto.randomUUID()}`,
            role: 'user',
            content: message,
            createdAt: new Date().toISOString(),
            references: [],
            warnings: [],
        }

        const conversationId = selectedConversation?.id
        if (!conversationId) return

        startTransition(() => {
            setLocalMessagesByConversation((current) => ({
                ...current,
                [conversationId]: [...(current[conversationId] ?? []), localUserMessage],
            }))
        })

        try {
            const assistantMessage = await sendMessageMutation.mutateAsync({ conversationId, message })
            startTransition(() => {
                setLocalMessagesByConversation((current) => ({
                    ...current,
                    [conversationId]: [...(current[conversationId] ?? []), assistantMessage],
                }))
            })
        } catch {
            // Mutation error handled by UI
        }
    }

    if (conversationsQuery.isLoading) {
        return <Card className="mx-4 my-6 h-[36rem] animate-pulse md:mx-6" />
    }

    if (conversationsQuery.isError) {
        return <Card className="mx-4 my-6 text-sm text-error-700 dark:text-error-300 md:mx-6">{conversationsQuery.error.message}</Card>
    }

    return (
        <div className="relative min-h-[calc(100vh-5.5rem)] overflow-hidden">
            <div className="absolute inset-0 surface-grid opacity-60 dark:opacity-30" />

            <div className="absolute left-4 top-4 z-20 flex items-center gap-2 md:left-6 md:top-6">
                <Button variant="secondary" size="sm" aria-label="Lịch sử" onClick={() => setIsHistoryOpen((current) => !current)}>
                    {isHistoryOpen ? <ChevronLeft size={16} /> : <History size={16} />}
                    <span className="hidden sm:inline">Lịch sử</span>
                </Button>

                {activeReferenceCount > 0 ? (
                    <Button variant="secondary" size="sm" aria-label="Nguồn tài liệu" onClick={() => setIsReferencePanelOpen((current) => !current)}>
                        <BookOpenText size={16} />
                        <span className="hidden sm:inline">Nguồn tài liệu</span>
                    </Button>
                ) : null}
            </div>

            <AnimatePresence>
                {isHistoryOpen ? (
                    <>
                        <motion.button
                            type="button"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setIsHistoryOpen(false)}
                            className="absolute inset-0 z-10 bg-brand-950/10 backdrop-blur-[2px] md:hidden"
                            aria-label="Đóng lịch sử"
                        />
                        <motion.aside
                            initial={{ x: -28, opacity: 0 }}
                            animate={{ x: 0, opacity: 1 }}
                            exit={{ x: -28, opacity: 0 }}
                            transition={{ duration: 0.2, ease: 'easeOut' }}
                            className="absolute left-0 top-0 z-20 flex h-full w-full max-w-[22rem] flex-col gap-4 border-r border-white/60 bg-white/92 p-4 shadow-theme-lg backdrop-blur-xl dark:border-white/8 dark:bg-[#0a1220]/92 md:p-5"
                        >
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-600">Lịch sử</div>
                                    <div className="text-lg font-semibold text-gray-950 dark:text-white">Các chủ đề gần đây</div>
                                </div>
                                <Button variant="ghost" size="sm" onClick={() => setIsHistoryOpen(false)}>
                                    <ChevronLeft size={16} />
                                </Button>
                            </div>

                            <div className="space-y-3">
                                <div className="relative">
                                    <Input
                                        value={conversationSearch}
                                        onChange={(event) => setConversationSearch(event.target.value)}
                                        placeholder="Tìm trong lịch sử..."
                                        className="pl-11"
                                    />
                                    <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
                                </div>
                                <Button variant="outline" fullWidth onClick={startFreshChat}>
                                    <Sparkles size={16} />
                                    Cuộc trò chuyện mới
                                </Button>
                            </div>

                            <div className="custom-scrollbar flex-1 space-y-2 overflow-y-auto pr-1">
                                {filteredConversations.map((conversation) => {
                                    const isActive = canvasMode === 'history' && selectedConversation?.id === conversation.id

                                    return (
                                        <button
                                            key={conversation.id}
                                            type="button"
                                            onClick={() => openHistoryConversation(conversation.id)}
                                            className={cn(
                                                'w-full rounded-[1.4rem] border px-4 py-3 text-left transition-all duration-200',
                                                isActive
                                                    ? 'border-brand-200 bg-brand-50 shadow-theme-sm dark:border-brand-800 dark:bg-brand-950/60'
                                                    : 'border-transparent bg-white/70 hover:border-gray-200 hover:bg-white dark:bg-white/[0.03] dark:hover:border-white/10 dark:hover:bg-white/[0.05]',
                                            )}
                                        >
                                            <div className="line-clamp-1 text-[15px] font-semibold text-gray-950 dark:text-white">{conversation.title}</div>
                                            <div className="mt-1 flex items-center gap-2">
                                                <div className="text-xs font-medium text-gray-500 dark:text-gray-400">{formatDateTime(conversation.updatedAt)}</div>
                                                <div className="h-1 w-1 rounded-full bg-gray-300 dark:bg-gray-600" />
                                                <div className="text-xs font-medium text-gray-500 dark:text-gray-400">{conversation.messages.length} tin nhắn</div>
                                            </div>
                                        </button>
                                    )
                                })}
                            </div>
                        </motion.aside>
                    </>
                ) : null}

                {isReferencePanelOpen ? (
                    <>
                        <motion.button
                            type="button"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setIsReferencePanelOpen(false)}
                            className="absolute inset-0 z-10 bg-brand-950/10 backdrop-blur-[2px] xl:hidden"
                            aria-label="Đóng nguồn tài liệu"
                        />
                        <motion.aside
                            initial={{ x: 28, opacity: 0 }}
                            animate={{ x: 0, opacity: 1 }}
                            exit={{ x: 28, opacity: 0 }}
                            transition={{ duration: 0.2, ease: 'easeOut' }}
                            className="absolute right-0 top-0 z-20 flex h-full w-full max-w-[22rem] flex-col gap-4 border-l border-white/60 bg-white/92 p-4 shadow-theme-lg backdrop-blur-xl dark:border-white/8 dark:bg-[#0a1220]/92 md:p-5"
                        >
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-600">Trích dẫn</div>
                                    <div className="text-lg font-semibold text-gray-950 dark:text-white">Nguồn tài liệu ({activeReferenceCount})</div>
                                </div>
                                <Button variant="ghost" size="sm" onClick={() => setIsReferencePanelOpen(false)}>
                                    <ChevronRight size={16} />
                                </Button>
                            </div>

                            <div className="custom-scrollbar flex-1 space-y-4 overflow-y-auto pr-1">
                                {activeReferenceMessage?.references.map((reference) => {
                                    const meta = getReferenceStatusMeta(reference.statusLabel)

                                    return (
                                        <RouteIntentLink
                                            key={reference.id}
                                            to={reference.href}
                                            className={cn(
                                                'block rounded-[1.4rem] border p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-theme-sm',
                                                meta.cardClassName,
                                            )}
                                        >
                                            <div className="space-y-3">
                                                <div className="space-y-1">
                                                    <div className="text-base font-semibold text-gray-950 dark:text-white">{reference.title}</div>
                                                    <p className="text-sm leading-6 text-gray-600 dark:text-gray-300">{reference.excerpt}</p>
                                                </div>
                                                <div className="flex items-center justify-between gap-3">
                                                    <Badge tone={meta.tone}>{meta.label}</Badge>
                                                    <span className="text-xs font-medium text-gray-500">Mở chi tiết</span>
                                                </div>
                                            </div>
                                        </RouteIntentLink>
                                    )
                                })}
                            </div>
                        </motion.aside>
                    </>
                ) : null}
            </AnimatePresence>

            <div className="relative z-[1] mx-auto flex min-h-[calc(100vh-5.5rem)] max-w-6xl flex-col px-4 pb-6 pt-24 md:px-8 md:pb-8">
                {showWelcomeCanvas ? (
                    <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center gap-8 pb-16 text-center">
                        <div className="space-y-4">
                            <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-[2rem] bg-brand-600 text-white shadow-theme-md animate-soft-pulse">
                                <Sparkles size={30} />
                            </div>
                            <div className="space-y-3">
                                <h1 className="text-4xl font-bold tracking-tight text-gray-950 dark:text-white md:text-5xl">UIT AI</h1>
                                <p className="mx-auto max-w-2xl text-base leading-8 text-gray-500">
                                    Một màn chat duy nhất để hỏi nhanh, xem câu trả lời gọn và chỉ mở `Nguồn tài liệu` khi thực sự cần kiểm tra trích dẫn.
                                </p>
                            </div>
                        </div>

                        <div className="flex w-full flex-wrap justify-center gap-3">
                            {quickPrompts.map((prompt) => {
                                const Icon = prompt.icon

                                return (
                                    <button
                                        key={prompt.label}
                                        type="button"
                                        onClick={() => setDraft(prompt.label)}
                                        className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white/92 px-4 py-2.5 text-sm font-semibold text-gray-700 shadow-theme-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-200 hover:text-brand-700 hover:shadow-theme-sm dark:border-gray-700 dark:bg-gray-900/92 dark:text-gray-200 dark:hover:border-brand-800 dark:hover:text-brand-200"
                                    >
                                        <Icon size={16} />
                                        {prompt.label}
                                    </button>
                                )
                            })}
                        </div>
                    </div>
                ) : (
                    <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col">
                        <div className="custom-scrollbar flex-1 space-y-6 overflow-y-auto pb-8 pt-4">
                            {displayedMessages.map((message) =>
                                message.role === 'assistant' ? (
                                    <AssistantMessage
                                        key={message.id}
                                        message={message}
                                        onOpenSources={(messageId) => {
                                            setActiveReferenceMessageId(messageId)
                                            setIsReferencePanelOpen(true)
                                        }}
                                    />
                                ) : (
                                    <UserMessage key={message.id} message={message} />
                                ),
                            )}

                            {sendMessageMutation.isPending || streamChat.isLoading ? <TypingIndicator /> : null}
                            <div ref={messageEndRef} />
                        </div>
                    </div>
                )}

                {sendMessageMutation.isError ? (
                    <div className="mx-auto mb-4 w-full max-w-4xl rounded-2xl border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-700 dark:border-error-900 dark:bg-error-950/40 dark:text-error-300">
                        {sendMessageMutation.error.message}
                    </div>
                ) : null}

                <div className="mx-auto mt-auto w-full max-w-4xl">
                    <div className="rounded-[2rem] border border-white/70 bg-white/92 p-3 shadow-theme-lg backdrop-blur-sm dark:border-white/8 dark:bg-[#162236]/92">
                        <div className="flex flex-col gap-3 md:flex-row md:items-end">
                            <div className="min-w-0 flex-1">
                                <label htmlFor="chat-draft" className="mb-2 block text-sm font-semibold text-gray-700 dark:text-gray-200">
                                    Hỏi UIT AI
                                </label>
                                <Input
                                    id="chat-draft"
                                    value={draft}
                                    onChange={(event) => setDraft(event.target.value)}
                                    onKeyDown={(event) => {
                                        if (event.key === 'Enter' && !event.shiftKey) {
                                            event.preventDefault()
                                            void sendDraftMessage()
                                        }
                                    }}
                                    placeholder="Nhập câu hỏi về học vụ, học phí, học bổng hoặc tài liệu nội bộ..."
                                />
                            </div>

                            <Button size="lg" className="md:min-w-32" onClick={() => void sendDraftMessage()} disabled={!draft.trim() || streamChat.isLoading}>
                                <Send size={16} />
                                Gửi
                            </Button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
