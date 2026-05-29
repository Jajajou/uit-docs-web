import { useStream } from '@langchain/langgraph-sdk/react'
import { startTransition, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
    ArrowRight,
    BookMarked,
    BookOpenText,
    CalendarDays,
    ChevronLeft,
    GraduationCap,
    LogOut,
    Menu,
    Moon,
    Paperclip,
    Search,
    Send,
    Sparkles,
    Square,
    Sun,
    Trash2,
    X,
} from 'lucide-react'
import { canAccessPath, getExperienceRoleLabel } from '@/app/config/routes'
import { RouteIntentLink } from '@/app/router/RouteIntentLink'
import { useLogoutSessionMutation, useSessionQuery } from '@/entities/auth/queries'
import { useSessionStore } from '@/entities/auth/store'
import {
    useClearConversationsMutation,
    useConversationsQuery,
    useDeleteConversationMutation,
    usePersistLiveChatMessageMutation,
    useSendChatMessageMutation,
} from '@/entities/chat/queries'
import {
    buildLangGraphSubmissionMessages,
    buildPersistLiveChatPayload,
    getLangGraphStreamConfig,
    getLatestAssistantStreamText,
} from '@/entities/chat/live'
import type { AnswerReference, Conversation, Message } from '@/entities/chat/types'
import { useThemeStore } from '@/entities/preferences/theme'
import { cn } from '@/shared/lib/cn'
import { Badge, BrandLoadingAnimation, BrandMark, Button, Card, Input } from '@/shared/ui'

const quickPrompts = [
    { label: 'Học phí học kỳ này được tính như thế nào?', icon: GraduationCap },
    { label: 'Lịch đăng ký môn học của khóa 2024 có thay đổi không?', icon: CalendarDays },
    { label: 'Điều kiện học bổng hiện tại là gì?', icon: BookOpenText },
]

const workspaceLinks = [
    { path: '/chat', label: 'Chat' },
    { path: '/documents', label: 'Thư viện' },
    { path: '/upload', label: 'Tải lên' },
    { path: '/manager', label: 'Quản trị' },
]

const SIDEBAR_WIDTH_CLASS = 'xl:pl-[22rem]'
const COMPOSER_MAX_HEIGHT = 176

type AssistantContentBlock =
    | {
          kind: 'paragraph'
          title?: string
          content: string
      }
    | {
          kind: 'list'
          title?: string
          items: string[]
      }

type ChatCanvasMode = 'fresh' | 'history'

interface ConversationSection {
    label: string
    conversations: Conversation[]
}

interface PendingLiveRequest {
    mode: ChatCanvasMode
    conversationId?: string
    localUserMessageId: string
    message: string
    requestMessage: string
}

function isDesktopSidebarViewport() {
    return typeof window !== 'undefined' && window.innerWidth >= 1280
}

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
            cardClassName: 'border-success-200 bg-success-50/85 dark:border-success-900 dark:bg-success-950/30',
        }
    }

    if (lower.includes('pending') || lower.includes('review')) {
        return {
            tone: 'warning' as const,
            label: 'Chờ rà soát',
            cardClassName: 'border-warning-200 bg-warning-50/85 dark:border-warning-900 dark:bg-warning-950/30',
        }
    }

    if (lower.includes('archive') || lower.includes('superseded') || lower.includes('expired')) {
        return {
            tone: 'neutral' as const,
            label: 'Đã thay thế',
            cardClassName: 'border-gray-200 bg-gray-50/92 dark:border-gray-800 dark:bg-gray-900/90',
        }
    }

    return {
        tone: 'brand' as const,
        label: statusLabel,
        cardClassName: 'border-brand-200 bg-brand-50/85 dark:border-brand-800 dark:bg-brand-950/30',
    }
}

function getTrustBadgeLabel(message: Message) {
    if (message.warnings.length > 0) {
        return 'Cần đối chiếu thêm'
    }

    if (message.references.length >= 2) {
        return `Đã đối chiếu ${message.references.length} nguồn`
    }

    if (message.references.length === 1) {
        return 'Đã đối chiếu 1 nguồn'
    }

    return 'Trả lời tham chiếu'
}

function formatAssistantContent(content: string) {
    return content
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1')
        .replace(/(?<!\*)\*\*(.+?)\*\*(?!\*)/gs, '$1')
        .replace(/(?<!_)__(.+?)__(?!_)/gs, '$1')
        .replace(/`([^`]+)`/g, '$1')
        .replace(/^[ \t]*#{1,6}[ \t]*/gm, '')
        .replace(/^[ \t]*>[ \t]?/gm, '')
        .replace(/\*\*/g, '')
        .replace(/__/g, '')
        .replace(/[ \t]+\n/g, '\n')
        .replace(/\n{3,}/g, '\n\n')
        .trim()
}

function normalizeAssistantHeading(line: string) {
    return line.trim().replace(/^[\u{1F449}\u261D\uFE0F\u2705\u2757\uFE0F\u27A1\uFE0F\u2022]+\s*/u, '')
}

function normalizeComparableText(value?: string) {
    return (value ?? '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-zA-Z0-9\s]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .toLowerCase()
}

function isConclusionHeading(title?: string) {
    const normalizedTitle = normalizeComparableText(title)
    return normalizedTitle === 'ket luan' || normalizedTitle === 'ket luan nhanh'
}

function parseAssistantParagraph(paragraph: string): AssistantContentBlock | null {
    const lines = paragraph
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)

    if (!lines.length) {
        return null
    }

    const [firstLine, ...remainingLines] = lines
    const normalizedHeading = normalizeAssistantHeading(firstLine)
    const hasSectionTitle = normalizedHeading.endsWith(':') && normalizedHeading.length <= 84
    const title = hasSectionTitle ? normalizedHeading.slice(0, -1).trim() : undefined
    const bodyLines = hasSectionTitle ? remainingLines : lines

    if (!bodyLines.length) {
        return null
    }

    if (bodyLines.every((line) => /^[-*\u2022]\s+/.test(line))) {
        return {
            kind: 'list',
            title,
            items: bodyLines.map((line) => line.replace(/^[-*\u2022]\s+/, '').trim()),
        }
    }

    return {
        kind: 'paragraph',
        title,
        content: bodyLines.join('\n'),
    }
}

function buildAssistantAnswer(content: string) {
    const normalizedContent = formatAssistantContent(content)
    const paragraphs = normalizedContent
        .split(/\n{2,}/)
        .map((paragraph) => paragraph.trim())
        .filter(Boolean)

    const [summaryParagraph = '', ...detailParagraphs] = paragraphs
    const detailBlocks = detailParagraphs.map(parseAssistantParagraph).filter(Boolean) as AssistantContentBlock[]

    return {
        summary: summaryParagraph,
        details: detailBlocks.filter((block) => !(summaryParagraph && isConclusionHeading(block.title))),
    }
}

function getConversationSectionLabel(updatedAt: string) {
    const today = new Date()
    const currentStart = new Date(today.getFullYear(), today.getMonth(), today.getDate())
    const updated = new Date(updatedAt)
    const updatedStart = new Date(updated.getFullYear(), updated.getMonth(), updated.getDate())
    const diffDays = Math.round((currentStart.getTime() - updatedStart.getTime()) / 86_400_000)

    if (diffDays <= 0) {
        return 'Hôm nay'
    }

    if (diffDays === 1) {
        return 'Hôm qua'
    }

    if (diffDays < 7) {
        return '7 ngày trước'
    }

    return 'Trước đó'
}

function groupConversationsByDate(conversations: Conversation[]) {
    const sectionOrder = ['Hôm nay', 'Hôm qua', '7 ngày trước', 'Trước đó']
    const grouped = new Map<string, Conversation[]>()

    for (const conversation of conversations) {
        const label = getConversationSectionLabel(conversation.updatedAt)
        grouped.set(label, [...(grouped.get(label) ?? []), conversation])
    }

    return sectionOrder
        .map((label) => ({
            label,
            conversations: grouped.get(label) ?? [],
        }))
        .filter((section) => section.conversations.length > 0)
}

function getConversationTimestamp(updatedAt: string) {
    const updated = new Date(updatedAt)
    const now = new Date()
    const sameDay =
        updated.getFullYear() === now.getFullYear() &&
        updated.getMonth() === now.getMonth() &&
        updated.getDate() === now.getDate()

    return sameDay
        ? new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit' }).format(updated)
        : new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit' }).format(updated)
}

function getReferenceKindLabel(reference: AnswerReference) {
    return reference.href.startsWith('/documents/') ? 'Hồ sơ tài liệu' : 'Nguồn web'
}

function getReferenceActionLabel(reference: AnswerReference) {
    return reference.href.startsWith('/documents/') ? 'Mở hồ sơ tài liệu' : 'Mở nguồn chi tiết'
}

function getMostRecentReference(messages: Message[]) {
    return [...messages]
        .reverse()
        .find((message) => message.role === 'assistant' && message.references.length > 0)
        ?.references[0] ?? null
}

function AssistantAnswerBody({ content }: { content: string }) {
    const answer = buildAssistantAnswer(content)

    return (
        <div className="space-y-4">
            {answer.summary ? (
                <div className="rounded-[1.5rem] border border-brand-100 bg-brand-50/85 px-4 py-4 shadow-theme-xs dark:border-brand-900 dark:bg-brand-950/35">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-700 dark:text-brand-200">
                        Kết luận nhanh
                    </div>
                    <p className="mt-2 text-[15px] font-medium leading-7 text-gray-900 dark:text-white">{answer.summary}</p>
                </div>
            ) : null}

            {answer.details.map((block, index) => (
                <section key={`${block.kind}-${index}`} className="space-y-2">
                    {block.title ? (
                        <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-gray-500 dark:text-gray-300">
                            {block.title}
                        </h3>
                    ) : null}

                    {block.kind === 'list' ? (
                        <ul className="space-y-2 pl-5 text-[15px] leading-7 text-gray-700 marker:text-brand-500 dark:text-gray-100">
                            {block.items.map((item) => (
                                <li key={item}>{item}</li>
                            ))}
                        </ul>
                    ) : (
                        <p className="whitespace-pre-wrap text-[15px] leading-7 text-gray-700 dark:text-gray-100">{block.content}</p>
                    )}
                </section>
            ))}
        </div>
    )
}

function CitationPreview({ reference, index }: { reference: AnswerReference; index: number }) {
    const meta = getReferenceStatusMeta(reference.statusLabel)

    return (
        <div className="group relative">
            <button
                type="button"
                aria-label={`Nguồn ${index + 1}: ${reference.title}`}
                className="inline-flex h-8 min-w-8 items-center justify-center rounded-full border border-brand-200 bg-brand-50/92 px-2 text-[11px] font-semibold text-brand-700 transition-all duration-150 hover:-translate-y-0.5 hover:border-brand-300 hover:bg-brand-100 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-500/15 dark:border-brand-800 dark:bg-brand-950/50 dark:text-brand-200 dark:hover:border-brand-700 dark:hover:bg-brand-950/70"
            >
                [{index + 1}]
            </button>

            <div className="pointer-events-none invisible absolute bottom-full left-0 z-20 mb-3 w-[19rem] max-w-[calc(100vw-4rem)] translate-y-2 opacity-0 transition-all duration-150 group-hover:pointer-events-auto group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:visible group-focus-within:translate-y-0 group-focus-within:opacity-100">
                <div className={cn('rounded-[1.45rem] border p-4 shadow-[0_26px_80px_rgba(15,23,42,0.18)] backdrop-blur-xl dark:shadow-[0_26px_90px_rgba(0,0,0,0.35)]', meta.cardClassName)}>
                    <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400">{`Nguồn ${index + 1}`}</div>
                            <div className="text-sm font-semibold text-gray-950 dark:text-white">{reference.title}</div>
                        </div>
                        <Badge tone={meta.tone}>{meta.label}</Badge>
                    </div>

                    <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{reference.excerpt}</p>

                    <div className="mt-4 flex items-center justify-between gap-3 border-t border-white/60 pt-3 text-xs dark:border-white/10">
                        <span className="font-semibold uppercase tracking-[0.14em] text-gray-400">{getReferenceKindLabel(reference)}</span>
                        <RouteIntentLink
                            to={reference.href}
                            className="inline-flex items-center gap-1.5 font-semibold text-brand-700 transition-colors hover:text-brand-800 dark:text-brand-200 dark:hover:text-brand-100"
                        >
                            {getReferenceActionLabel(reference)}
                            <ArrowRight size={14} />
                        </RouteIntentLink>
                    </div>
                </div>
            </div>
        </div>
    )
}

function AssistantMessage({ message }: { message: Message }) {
    return (
        <div className="flex gap-4">
            <BrandMark className="mt-1 h-11 w-11 shrink-0 rounded-2xl" />
            <article className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-semibold text-gray-950 dark:text-white">UIT AI</div>
                    <Badge tone={getConfidenceTone(message.confidence)}>{getTrustBadgeLabel(message)}</Badge>
                </div>

                <div className="mt-3 rounded-[2rem] border border-white/75 bg-white/92 px-5 py-5 shadow-[0_24px_70px_rgba(15,23,42,0.08)] backdrop-blur-sm dark:border-white/8 dark:bg-[#101b2d]/92 dark:shadow-[0_24px_80px_rgba(0,0,0,0.25)]">
                    <AssistantAnswerBody content={message.content} />

                    {message.references.length > 0 ? (
                        <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-white/70 pt-4 dark:border-white/10">
                            <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400">Nguồn</span>
                            <div className="flex flex-wrap items-center gap-2">
                                {message.references.map((reference, index) => (
                                    <CitationPreview key={reference.id} reference={reference} index={index} />
                                ))}
                            </div>
                            <span className="text-xs text-gray-400">Bấm vào [1] để xem trích đoạn và mở hồ sơ gốc.</span>
                        </div>
                    ) : null}

                    {message.warnings.length > 0 ? (
                        <div className="mt-4 space-y-2 rounded-[1.4rem] border border-warning-200 bg-warning-50/80 px-4 py-3 dark:border-warning-900 dark:bg-warning-950/30">
                            {message.warnings.map((warning) => (
                                <p key={warning.code} className="text-sm leading-6 text-warning-800 dark:text-warning-100">
                                    {warning.message}
                                </p>
                            ))}
                        </div>
                    ) : null}
                </div>
            </article>
        </div>
    )
}

function TypingIndicator() {
    return (
        <div className="flex items-center gap-3 px-1 py-2 text-sm text-gray-500 dark:text-gray-300">
            <BrandMark className="h-10 w-10 shrink-0 rounded-[1.25rem]" />
            <div className="flex items-center gap-3">
                <span className="font-medium">UIT AI đang đối chiếu nguồn liên quan</span>
                <div className="flex items-center gap-1.5">
                    {[0, 1, 2].map((index) => (
                        <motion.span
                            // Staggered dots feel calmer than a boxed loader for long document retrieval.
                            key={index}
                            className="h-2 w-2 rounded-full bg-brand-400 dark:bg-brand-300"
                            animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }}
                            transition={{ duration: 1.05, repeat: Number.POSITIVE_INFINITY, delay: index * 0.16, ease: 'easeInOut' }}
                        />
                    ))}
                </div>
            </div>
        </div>
    )
}

function UserMessage({ message }: { message: Message }) {
    return (
        <div className="flex justify-end">
            <div className="max-w-[44rem] rounded-[1.8rem] border border-brand-100 bg-brand-50/90 px-5 py-4 text-[15px] leading-7 text-gray-800 shadow-theme-xs dark:border-brand-900 dark:bg-brand-950/40 dark:text-brand-50">
                {message.content}
            </div>
        </div>
    )
}

function HistorySidebarContent({
    canvasMode,
    selectedConversationId,
    conversationSearch,
    onConversationSearchChange,
    conversationSections,
    totalConversationCount,
    clearPending,
    deletePending,
    onStartFreshChat,
    onClearConversations,
    onOpenConversation,
    onDeleteConversation,
    workspaceLinks,
    activePath,
    roleLabel,
    userName,
    userDepartment,
    userEmail,
    avatarInitials,
    theme,
    onToggleTheme,
    logoutPending,
    onLogout,
    onClose,
}: {
    canvasMode: ChatCanvasMode
    selectedConversationId?: string
    conversationSearch: string
    onConversationSearchChange: (value: string) => void
    conversationSections: ConversationSection[]
    totalConversationCount: number
    clearPending: boolean
    deletePending: boolean
    onStartFreshChat: () => void
    onClearConversations: () => void
    onOpenConversation: (conversationId: string) => void
    onDeleteConversation: (conversationId: string) => void
    workspaceLinks: Array<{ path: string; label: string }>
    activePath: string
    roleLabel: string
    userName: string
    userDepartment: string
    userEmail: string
    avatarInitials: string
    theme: 'light' | 'dark'
    onToggleTheme: () => void
    logoutPending: boolean
    onLogout: () => void
    onClose?: () => void
}) {
    const shouldShowDepartment =
        Boolean(userDepartment) &&
        normalizeComparableText(userDepartment) !== normalizeComparableText(roleLabel) &&
        normalizeComparableText(userDepartment) !== 'student'

    return (
        <div className="flex h-full flex-col">
            <div className="border-b border-white/70 px-5 pb-5 pt-6 dark:border-white/10">
                <div className="flex items-start justify-between gap-3">
                    <RouteIntentLink to="/chat" className="min-w-0">
                        <div className="flex items-center gap-3">
                            <BrandMark className="h-14 w-14 rounded-[1.35rem]" label="UIT" />
                            <div className="min-w-0">
                                <div className="text-[0.66rem] font-semibold uppercase tracking-[0.32em] text-brand-500">UIT Portal</div>
                                <div className="truncate text-2xl font-bold tracking-tight text-gray-950 dark:text-white">UIT AI</div>
                            </div>
                        </div>
                    </RouteIntentLink>

                    {onClose ? (
                        <Button variant="ghost" size="sm" aria-label="Đóng lịch sử" onClick={onClose} className="xl:hidden">
                            <ChevronLeft size={18} />
                        </Button>
                    ) : null}
                </div>

                <Button className="mt-5 w-full justify-center" onClick={onStartFreshChat}>
                    <Sparkles size={16} />
                    Cuộc trò chuyện mới
                </Button>

                <div className="relative mt-4">
                    <Input
                        value={conversationSearch}
                        onChange={(event) => onConversationSearchChange(event.target.value)}
                        placeholder="Tìm trong lịch sử..."
                        className="pl-11"
                    />
                    <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
                </div>
            </div>

            <div className="custom-scrollbar flex-1 overflow-y-auto px-3 py-4">
                <div className="space-y-5">
                    {conversationSections.length === 0 ? (
                        <div className="rounded-[1.6rem] border border-dashed border-gray-200 bg-white/72 px-4 py-6 text-sm leading-6 text-gray-500 dark:border-white/10 dark:bg-white/[0.03] dark:text-gray-300">
                            Chưa có cuộc trò chuyện nào phù hợp. Hãy bắt đầu một chat mới để lưu lại lịch sử học vụ và tài liệu đã hỏi.
                        </div>
                    ) : (
                        conversationSections.map((section) => (
                            <section key={section.label} className="space-y-2">
                                <div className="px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-400">{section.label}</div>
                                <div className="space-y-1.5">
                                    {section.conversations.map((conversation) => {
                                        const isActive = canvasMode === 'history' && selectedConversationId === conversation.id
                                        const latestMessage = conversation.messages[conversation.messages.length - 1]?.content ?? 'Chưa có nội dung'

                                        return (
                                            <div
                                                key={conversation.id}
                                                className={cn(
                                                    'group flex items-start gap-3 rounded-[1.45rem] border px-3 py-3 transition-all duration-200',
                                                    isActive
                                                        ? 'border-brand-200 bg-brand-50 shadow-theme-xs dark:border-brand-800 dark:bg-brand-950/45'
                                                        : 'border-transparent bg-white/72 hover:border-gray-200 hover:bg-white dark:bg-white/[0.03] dark:hover:border-white/10 dark:hover:bg-white/[0.05]',
                                                )}
                                            >
                                                <button
                                                    type="button"
                                                    onClick={() => onOpenConversation(conversation.id)}
                                                    className="min-w-0 flex-1 text-left"
                                                >
                                                    <div className="flex items-start justify-between gap-3">
                                                        <div className="truncate text-sm font-semibold text-gray-950 dark:text-white">{conversation.title}</div>
                                                        <div className="shrink-0 text-[11px] text-gray-400">{getConversationTimestamp(conversation.updatedAt)}</div>
                                                    </div>
                                                    <p className="mt-1 line-clamp-2 text-sm leading-6 text-gray-500 dark:text-gray-300">{latestMessage}</p>
                                                </button>

                                                <button
                                                    type="button"
                                                    onClick={() => void onDeleteConversation(conversation.id)}
                                                    disabled={deletePending}
                                                    aria-label={`Xóa ${conversation.title}`}
                                                    className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-gray-400 transition-colors hover:bg-white hover:text-error-600 disabled:opacity-40 dark:hover:bg-white/10 dark:hover:text-error-300"
                                                >
                                                    <Trash2 size={15} />
                                                </button>
                                            </div>
                                        )
                                    })}
                                </div>
                            </section>
                        ))
                    )}
                </div>
            </div>

            <div className="border-t border-white/70 px-4 pb-4 pt-4 dark:border-white/10">
                <div className="flex items-center justify-between gap-3 rounded-[1.5rem] border border-white/70 bg-white/82 px-4 py-3 shadow-theme-xs dark:border-white/10 dark:bg-white/[0.04]">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-400">Khu vực làm việc</div>
                    {totalConversationCount > 0 ? (
                        <button
                            type="button"
                            onClick={onClearConversations}
                            disabled={clearPending}
                            className="text-xs font-semibold text-gray-500 transition-colors hover:text-error-600 disabled:opacity-40 dark:text-gray-300 dark:hover:text-error-300"
                        >
                            Xóa lịch sử
                        </button>
                    ) : null}
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2">
                    {workspaceLinks.map((item) => {
                        const isActive =
                            activePath === item.path ||
                            (item.path === '/chat' && (activePath === '/' || activePath === '/chat')) ||
                            (item.path === '/documents' && activePath.startsWith('/documents'))

                        return (
                            <RouteIntentLink
                                key={item.path}
                                to={item.path}
                                className={cn(
                                    'inline-flex min-w-0 items-center justify-center rounded-[1.2rem] border px-3 py-2.5 text-sm font-semibold transition-all duration-200',
                                    isActive
                                        ? 'border-brand-200 bg-brand-50 text-brand-700 shadow-theme-xs dark:border-brand-800 dark:bg-brand-950/55 dark:text-brand-200'
                                        : 'border-gray-200 bg-white/92 text-gray-600 hover:border-brand-200 hover:text-brand-700 dark:border-gray-700 dark:bg-gray-900/92 dark:text-gray-200 dark:hover:border-brand-800 dark:hover:text-brand-200',
                                )}
                            >
                                <span className="truncate">{item.label}</span>
                            </RouteIntentLink>
                        )
                    })}
                </div>

                <div className="mt-4 rounded-[1.7rem] border border-white/75 bg-white/92 p-4 shadow-[0_18px_50px_rgba(15,23,42,0.08)] dark:border-white/10 dark:bg-[#0d1728]/92">
                    <div className="flex items-start gap-3">
                        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[1.25rem] border border-brand-100 bg-brand-50 text-sm font-semibold text-brand-700 dark:border-brand-900 dark:bg-brand-950/45 dark:text-brand-200">
                            {avatarInitials}
                        </div>
                        <div className="min-w-0">
                            <div className="truncate text-sm font-semibold text-gray-950 dark:text-white">{userName}</div>
                            <div className="mt-1 flex flex-wrap items-center gap-2">
                                <Badge tone="brand">{roleLabel}</Badge>
                                {shouldShowDepartment ? (
                                    <span className="text-xs text-gray-500 dark:text-gray-300">{userDepartment}</span>
                                ) : null}
                            </div>
                            <div className="mt-2 truncate text-xs text-gray-500 dark:text-gray-300">{userEmail}</div>
                        </div>
                    </div>

                    <div className="mt-4 grid grid-cols-2 gap-2">
                        <Button variant="secondary" size="sm" onClick={onToggleTheme} aria-label="Đổi giao diện sáng tối">
                            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
                            <span>{theme === 'dark' ? 'Sáng' : 'Tối'}</span>
                        </Button>

                        <Button variant="secondary" size="sm" isLoading={logoutPending} onClick={onLogout}>
                            <LogOut size={16} />
                            <span>Đăng xuất</span>
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    )
}

export function ChatWorkspace({ scenario }: { scenario?: string }) {
    const conversationsQuery = useConversationsQuery({ scenario })
    const sendMessageMutation = useSendChatMessageMutation({ scenario })
    const persistLiveMessageMutation = usePersistLiveChatMessageMutation({ scenario })
    const deleteConversationMutation = useDeleteConversationMutation({ scenario })
    const clearConversationsMutation = useClearConversationsMutation({ scenario })
    const sessionQuery = useSessionQuery({ scenario })
    const logoutMutation = useLogoutSessionMutation()

    const selectedRole = useSessionStore((state) => state.selectedRole)
    const theme = useThemeStore((state) => state.theme)
    const toggleTheme = useThemeStore((state) => state.toggleTheme)
    const liveStreamConfig = useMemo(() => getLangGraphStreamConfig(), [])

    const [selectedConversationId, setSelectedConversationId] = useState('')
    const [canvasMode, setCanvasMode] = useState<ChatCanvasMode>('fresh')
    const [draft, setDraft] = useState('')
    const [conversationSearch, setConversationSearch] = useState('')
    const [localMessagesByConversation, setLocalMessagesByConversation] = useState<Record<string, Message[]>>({})
    const [freshConversationPreview, setFreshConversationPreview] = useState<Conversation | null>(null)
    const [freshMessages, setFreshMessages] = useState<Message[]>([])
    const [isHistoryOpen, setIsHistoryOpen] = useState(isDesktopSidebarViewport())
    const [composerContextReference, setComposerContextReference] = useState<AnswerReference | null>(null)
    const [generationNotice, setGenerationNotice] = useState<string | null>(null)
    const [pendingLiveRequest, setPendingLiveRequest] = useState<PendingLiveRequest | null>(null)
    const [isLiveTransportAvailable, setIsLiveTransportAvailable] = useState<boolean | null>(
        liveStreamConfig.enabled ? null : false,
    )

    const deferredConversationSearch = useDeferredValue(conversationSearch)
    const messagesViewportRef = useRef<HTMLDivElement | null>(null)
    const messageEndRef = useRef<HTMLDivElement | null>(null)
    const composerTextareaRef = useRef<HTMLTextAreaElement | null>(null)
    const activeRequestControllerRef = useRef<AbortController | null>(null)
    const hasHydratedInitialConversationRef = useRef(false)
    const wasPendingRef = useRef(false)

    const session = sessionQuery.data
    const roleLabel = getExperienceRoleLabel(session?.user.role ?? selectedRole)
    const availableWorkspaceLinks = workspaceLinks.filter((item) => canAccessPath(session?.user.role ?? selectedRole, item.path))

    const scrollChatToBottom = (behavior: ScrollBehavior = 'smooth') => {
        requestAnimationFrame(() => {
            if (messagesViewportRef.current) {
                messagesViewportRef.current.scrollTo({
                    top: messagesViewportRef.current.scrollHeight,
                    behavior,
                })
            }

            messageEndRef.current?.scrollIntoView({ behavior, block: 'end' })
        })
    }

    const conversations = useMemo(() => {
        const serverConversations = conversationsQuery.data ?? []

        if (!freshConversationPreview || serverConversations.some((conversation) => conversation.id === freshConversationPreview.id)) {
            return serverConversations
        }

        return [freshConversationPreview, ...serverConversations]
    }, [conversationsQuery.data, freshConversationPreview])

    useEffect(() => {
        if (!freshConversationPreview || !conversationsQuery.data?.some((conversation) => conversation.id === freshConversationPreview.id)) {
            return
        }

        setFreshConversationPreview(null)
    }, [conversationsQuery.data, freshConversationPreview])

    useEffect(() => {
        if (!conversationsQuery.data?.length) {
            return
        }

        setLocalMessagesByConversation((current) => {
            let changed = false
            const next = { ...current }

            for (const [conversationId, optimisticMessages] of Object.entries(current)) {
                if (!optimisticMessages.length) {
                    continue
                }

                const serverConversation = conversationsQuery.data.find((conversation) => conversation.id === conversationId)
                const latestAssistantMessage = [...optimisticMessages].reverse().find((message) => message.role === 'assistant')

                if (!serverConversation || !latestAssistantMessage) {
                    continue
                }

                const hasServerEcho = serverConversation.messages.some(
                    (message) =>
                        message.role === 'assistant' &&
                        message.content === latestAssistantMessage.content &&
                        message.createdAt === latestAssistantMessage.createdAt,
                )

                if (hasServerEcho) {
                    delete next[conversationId]
                    changed = true
                }
            }

            return changed ? next : current
        })
    }, [conversationsQuery.data])

    useEffect(() => {
        if (!conversations.length) {
            setSelectedConversationId('')
            return
        }

        if (!conversations.some((conversation) => conversation.id === selectedConversationId)) {
            setSelectedConversationId(conversations[0].id)
        }

        if (!hasHydratedInitialConversationRef.current && freshMessages.length === 0) {
            hasHydratedInitialConversationRef.current = true
            setCanvasMode('history')
        }
    }, [conversations, freshMessages.length, selectedConversationId])

    const filteredConversations = useMemo(() => {
        if (!conversations.length) {
            return []
        }

        const normalizedSearch = deferredConversationSearch.trim().toLowerCase()
        if (!normalizedSearch) {
            return conversations
        }

        return conversations.filter((conversation) => {
            const titleMatches = conversation.title.toLowerCase().includes(normalizedSearch)
            const contentMatches = conversation.messages.some((message) => message.content.toLowerCase().includes(normalizedSearch))
            return titleMatches || contentMatches
        })
    }, [conversations, deferredConversationSearch])

    const conversationSections = useMemo(() => groupConversationsByDate(filteredConversations), [filteredConversations])

    const selectedConversation = useMemo(
        () => conversations.find((conversation) => conversation.id === selectedConversationId) ?? filteredConversations[0],
        [conversations, filteredConversations, selectedConversationId],
    )

    const hasServerConversationSelected = Boolean(
        selectedConversation && conversationsQuery.data?.some((conversation) => conversation.id === selectedConversation.id),
    )

    const historyMessages = useMemo(() => {
        if (!selectedConversation) {
            return []
        }

        return [
            ...selectedConversation.messages,
            ...(hasServerConversationSelected ? localMessagesByConversation[selectedConversation.id] ?? [] : []),
        ]
    }, [hasServerConversationSelected, localMessagesByConversation, selectedConversation])

    const displayedMessages = canvasMode === 'fresh' ? freshMessages : historyMessages
    const liveStream = useStream<Record<string, unknown>>({
        transport: liveStreamConfig.transport!,
        initialValues: {},
    })
    const isLiveStreamPending = Boolean(pendingLiveRequest) && liveStream.isLoading
    const streamingAssistantText = useMemo(
        () => (isLiveStreamPending ? getLatestAssistantStreamText(liveStream.messages as unknown[], liveStream.values) : ''),
        [isLiveStreamPending, liveStream.messages, liveStream.values],
    )
    const streamingAssistantMessage = useMemo<Message | null>(() => {
        if (!streamingAssistantText) {
            return null
        }

        return {
            id: 'streaming-assistant-preview',
            role: 'assistant',
            content: streamingAssistantText,
            createdAt: new Date().toISOString(),
            references: [],
            warnings: [],
        }
    }, [streamingAssistantText])
    const displayedMessagesWithPreview = streamingAssistantMessage ? [...displayedMessages, streamingAssistantMessage] : displayedMessages
    const suggestedComposerReference = useMemo(() => getMostRecentReference(displayedMessages), [displayedMessages])

    useEffect(() => {
        setComposerContextReference((current) => {
            if (!current) {
                return current
            }

            const currentStillExists = displayedMessages.some((message) =>
                message.references.some((reference) => reference.id === current.id),
            )

            return currentStillExists ? current : null
        })
    }, [displayedMessages])

    useEffect(() => {
        const textarea = composerTextareaRef.current
        if (!textarea) {
            return
        }

        textarea.style.height = '0px'
        const nextHeight = Math.min(textarea.scrollHeight, COMPOSER_MAX_HEIGHT)
        textarea.style.height = `${Math.max(nextHeight, 56)}px`
        textarea.style.overflowY = textarea.scrollHeight > COMPOSER_MAX_HEIGHT ? 'auto' : 'hidden'
    }, [draft])

    useEffect(() => {
        return () => {
            activeRequestControllerRef.current?.abort()
        }
    }, [])

    useEffect(() => {
        const behavior: ScrollBehavior =
            isLiveStreamPending || sendMessageMutation.isPending || wasPendingRef.current || displayedMessagesWithPreview.length > 0
                ? 'smooth'
                : 'auto'

        scrollChatToBottom(behavior)
        wasPendingRef.current = isLiveStreamPending || sendMessageMutation.isPending
    }, [canvasMode, displayedMessagesWithPreview.length, isLiveStreamPending, selectedConversation?.id, sendMessageMutation.isPending])

    const showWelcomeCanvas = canvasMode === 'fresh' && displayedMessagesWithPreview.length === 0
    useEffect(() => {
        if (!liveStreamConfig.enabled) {
            setIsLiveTransportAvailable(false)
            return
        }

        let ignore = false
        const fetchLiveHealth = liveStreamConfig.fetch ?? fetch
        const healthUrl = `${liveStreamConfig.apiUrl.replace(/\/+$/, '')}/ok`

        void fetchLiveHealth(healthUrl, {
            headers: {
                Accept: 'application/json',
            },
        })
            .then((response) => {
                if (!ignore) {
                    setIsLiveTransportAvailable(response.ok)
                }
            })
            .catch(() => {
                if (!ignore) {
                    setIsLiveTransportAvailable(false)
                }
            })

        return () => {
            ignore = true
        }
    }, [liveStreamConfig.apiUrl, liveStreamConfig.enabled, liveStreamConfig.fetch])

    const liveStreamError =
        liveStream.error instanceof Error
            ? liveStream.error
            : liveStream.error
              ? new Error(String(liveStream.error))
              : null
    const surfacedLiveStreamError = generationNotice && liveStreamError ? null : liveStreamError
    const mutationError =
        surfacedLiveStreamError ??
        persistLiveMessageMutation.error ??
        sendMessageMutation.error ??
        deleteConversationMutation.error ??
        clearConversationsMutation.error ??
        logoutMutation.error ??
        null
    const canToggleComposerContext = Boolean(composerContextReference ?? suggestedComposerReference)
    const isResponding = isLiveStreamPending || persistLiveMessageMutation.isPending || sendMessageMutation.isPending

    const buildRequestMessage = (message: string) => {
        if (!composerContextReference) {
            return message
        }

        return `Ưu tiên đối chiếu tài liệu "${composerContextReference.title}" khi trả lời.\n\n${message}`
    }

    const toggleComposerContext = () => {
        setComposerContextReference((current) => {
            if (current) {
                return null
            }

            return suggestedComposerReference ?? null
        })
        setGenerationNotice(null)
    }

    const stopGeneration = () => {
        if (isLiveStreamPending) {
            void liveStream.stop()
            setPendingLiveRequest(null)
            setGenerationNotice('Đã dừng phản hồi. Bạn có thể chỉnh lại câu hỏi hoặc đổi nguồn rồi gửi lại.')
            return
        }

        if (!activeRequestControllerRef.current) {
            return
        }

        activeRequestControllerRef.current.abort()
        sendMessageMutation.reset()
        setGenerationNotice('Đã dừng phản hồi. Bạn có thể chỉnh lại câu hỏi hoặc đổi nguồn rồi gửi lại.')
    }

    const runChatRequest = async (payload: { conversationId?: string; message: string }) => {
        activeRequestControllerRef.current?.abort()
        sendMessageMutation.reset()

        const controller = new AbortController()
        activeRequestControllerRef.current = controller

        try {
            return await sendMessageMutation.mutateAsync({
                ...payload,
                signal: controller.signal,
            })
        } catch (error) {
            if (controller.signal.aborted) {
                sendMessageMutation.reset()
                return null
            }

            throw error
        } finally {
            if (activeRequestControllerRef.current === controller) {
                activeRequestControllerRef.current = null
            }
        }
    }

    const rollbackPendingLiveRequest = (request: PendingLiveRequest) => {
        if (request.mode === 'fresh') {
            startTransition(() => {
                setFreshMessages((current) => current.filter((item) => item.id !== request.localUserMessageId))
            })
        } else if (request.conversationId) {
            startTransition(() => {
                setLocalMessagesByConversation((current) => ({
                    ...current,
                    [request.conversationId!]: (current[request.conversationId!] ?? []).filter(
                        (item) => item.id !== request.localUserMessageId,
                    ),
                }))
            })
        }

        setDraft(request.message)
    }

    const buildPendingLocalUserMessage = (request: PendingLiveRequest): Message => ({
        id: request.localUserMessageId,
        role: 'user',
        content: request.message,
        createdAt: new Date().toISOString(),
        references: [],
        warnings: [],
    })

    const fallbackToStandardChatRequest = async (request: PendingLiveRequest) => {
        try {
            const response = await runChatRequest({
                conversationId: request.conversationId,
                message: request.requestMessage,
            })

            if (!response) {
                rollbackPendingLiveRequest(request)
                return
            }

            setGenerationNotice('Da chuyen sang che do tra loi du phong vi ket noi live tam thoi khong san sang.')

            if (request.mode === 'fresh') {
                const pendingLocalUserMessage = buildPendingLocalUserMessage(request)

                startTransition(() => {
                    const optimisticMessages = freshMessages.some((item) => item.id === request.localUserMessageId)
                        ? freshMessages
                        : [pendingLocalUserMessage]

                    setFreshConversationPreview({
                        id: response.conversationId,
                        title: request.message,
                        updatedAt: response.message.createdAt,
                        messages: [...optimisticMessages, response.message],
                    })
                    setSelectedConversationId(response.conversationId)
                    setCanvasMode('history')
                    setFreshMessages([])
                    if (!isDesktopSidebarViewport()) {
                        setIsHistoryOpen(false)
                    }
                })
                return
            }

            const conversationId = request.conversationId ?? response.conversationId
            startTransition(() => {
                setLocalMessagesByConversation((current) => ({
                    ...current,
                    [conversationId]: [...(current[conversationId] ?? []), response.message],
                }))
            })
        } catch {
            rollbackPendingLiveRequest(request)
        }
    }

    const runLiveChatRequest = async (payload: PendingLiveRequest & { history: Message[] }) => {
        // This deployment does not expose the thread hydration endpoints used by
        // the hosted SDK, so we submit the visible history each turn instead of
        // re-binding the client to a persisted remote thread.
        const submissionMessages = buildLangGraphSubmissionMessages(payload.history, payload.requestMessage)

        try {
            await liveStream.submit({
                messages: submissionMessages,
            })
        } catch {
            setIsLiveTransportAvailable(false)
            return false
        }

        setPendingLiveRequest({
            mode: payload.mode,
            conversationId: payload.conversationId,
            localUserMessageId: payload.localUserMessageId,
            message: payload.message,
            requestMessage: payload.requestMessage,
        })

        return true
    }

    useEffect(() => {
        if (!pendingLiveRequest || liveStream.isLoading || persistLiveMessageMutation.isPending) {
            return
        }

        const completedRequest = pendingLiveRequest
        setPendingLiveRequest(null)

        if (liveStreamError) {
            setIsLiveTransportAvailable(false)
            void fallbackToStandardChatRequest(completedRequest)
            return
        }

        void persistLiveMessageMutation
            .mutateAsync(
                buildPersistLiveChatPayload({
                    conversationId: completedRequest.conversationId,
                    message: completedRequest.requestMessage,
                    messages: liveStream.messages as unknown[],
                    values: liveStream.values,
                }),
            )
            .then((response) => {
                if (completedRequest.mode === 'fresh') {
                    startTransition(() => {
                        setFreshConversationPreview({
                            id: response.conversationId,
                            title: completedRequest.message,
                            updatedAt: response.message.createdAt,
                            messages: [...freshMessages, response.message],
                        })
                        setSelectedConversationId(response.conversationId)
                        setCanvasMode('history')
                        setFreshMessages([])
                        if (!isDesktopSidebarViewport()) {
                            setIsHistoryOpen(false)
                        }
                    })
                    return
                }

                const conversationId = completedRequest.conversationId ?? response.conversationId
                startTransition(() => {
                    setLocalMessagesByConversation((current) => ({
                        ...current,
                        [conversationId]: [...(current[conversationId] ?? []), response.message],
                    }))
                })
            })
            .catch(() => {
                void fallbackToStandardChatRequest(completedRequest)
            })
    }, [
        fallbackToStandardChatRequest,
        freshMessages,
        liveStream.isLoading,
        liveStream.messages,
        liveStream.values,
        liveStreamError,
        pendingLiveRequest,
        persistLiveMessageMutation,
    ])

    const toggleHistoryPanel = () => {
        startTransition(() => {
            setIsHistoryOpen((current) => !current)
        })
    }

    const startFreshChat = () => {
        setCanvasMode('fresh')
        setSelectedConversationId('')
        setFreshMessages([])
        setFreshConversationPreview(null)
        setPendingLiveRequest(null)
        setComposerContextReference(null)
        setGenerationNotice(null)
        setDraft('')
        if (!isDesktopSidebarViewport()) {
            setIsHistoryOpen(false)
        }
    }

    const openHistoryConversation = (conversationId: string) => {
        startTransition(() => {
            setSelectedConversationId(conversationId)
            setCanvasMode('history')
            setGenerationNotice(null)

            if (!isDesktopSidebarViewport()) {
                setIsHistoryOpen(false)
            }
        })
    }

    const handleDeleteConversation = async (conversationId: string) => {
        const remainingConversationId = conversations.find((conversation) => conversation.id !== conversationId)?.id ?? ''

        await deleteConversationMutation.mutateAsync(conversationId)

        startTransition(() => {
            setLocalMessagesByConversation((current) => {
                const next = { ...current }
                delete next[conversationId]
                return next
            })
            setFreshConversationPreview((current) => (current?.id === conversationId ? null : current))

            if (selectedConversationId === conversationId) {
                setSelectedConversationId(remainingConversationId)
                setCanvasMode(remainingConversationId ? 'history' : 'fresh')
            }
        })
    }

    const handleClearConversations = async () => {
        await clearConversationsMutation.mutateAsync()

        startTransition(() => {
            setLocalMessagesByConversation({})
            setFreshConversationPreview(null)
            setPendingLiveRequest(null)
            setSelectedConversationId('')
            setCanvasMode('fresh')
            setComposerContextReference(null)
            setGenerationNotice(null)
            setIsHistoryOpen(isDesktopSidebarViewport())
        })
    }

    const sendMessage = async (rawMessage: string) => {
        const message = rawMessage.trim()
        const shouldUseLiveStream =
            liveStreamConfig.enabled && isLiveTransportAvailable !== false && (!scenario || scenario === 'happy')

        if (!message || isResponding) {
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

        setGenerationNotice(null)
        setDraft('')
        const requestMessage = buildRequestMessage(message)

        if (canvasMode === 'fresh') {
            startTransition(() => {
                setFreshMessages((current) => [...current, localUserMessage])
            })

            try {
                if (shouldUseLiveStream) {
                    const startedLiveRequest = await runLiveChatRequest({
                        mode: 'fresh',
                        localUserMessageId: localUserMessage.id,
                        message,
                        requestMessage,
                        history: displayedMessages,
                    })
                    if (startedLiveRequest) {
                        return
                    }
                }

                const response = await runChatRequest({ message: requestMessage })
                if (!response) {
                    startTransition(() => {
                        setFreshMessages((current) => current.filter((item) => item.id !== localUserMessage.id))
                    })
                    setDraft(message)
                    return
                }

                startTransition(() => {
                    setFreshConversationPreview({
                        id: response.conversationId,
                        title: message,
                        updatedAt: response.message.createdAt,
                        messages: [localUserMessage, response.message],
                    })
                    setSelectedConversationId(response.conversationId)
                    setCanvasMode('history')
                    setFreshMessages([])
                    if (!isDesktopSidebarViewport()) {
                        setIsHistoryOpen(false)
                    }
                })
            } catch {
                // Mutation state already surfaces the error.
            }

            return
        }

        if (!selectedConversation) {
            startFreshChat()
            return
        }

        const conversationId = selectedConversation.id
        startTransition(() => {
            setLocalMessagesByConversation((current) => ({
                ...current,
                [conversationId]: [...(current[conversationId] ?? []), localUserMessage],
            }))
        })

        try {
            if (shouldUseLiveStream) {
                const startedLiveRequest = await runLiveChatRequest({
                    mode: 'history',
                    conversationId,
                    localUserMessageId: localUserMessage.id,
                    message,
                    requestMessage,
                    history: displayedMessages,
                })
                if (startedLiveRequest) {
                    return
                }
            }

            const response = await runChatRequest({ conversationId, message: requestMessage })
            if (!response) {
                startTransition(() => {
                    setLocalMessagesByConversation((current) => ({
                        ...current,
                        [conversationId]: (current[conversationId] ?? []).filter((item) => item.id !== localUserMessage.id),
                    }))
                })
                setDraft(message)
                return
            }

            startTransition(() => {
                setLocalMessagesByConversation((current) => ({
                    ...current,
                    [conversationId]: [...(current[conversationId] ?? []), response.message],
                }))
            })
        } catch {
            // Mutation state already surfaces the error.
        }
    }

    const sendDraftMessage = async () => {
        if (isResponding) {
            return
        }

        await sendMessage(draft)
    }

    const handleLogout = async () => {
        await logoutMutation.mutateAsync()
        window.location.replace('/auth/login')
    }

    if (conversationsQuery.isLoading || sessionQuery.isLoading) {
        return (
            <Card className="flex min-h-screen items-center justify-center border-none bg-transparent p-6 shadow-none">
                <BrandLoadingAnimation
                    title="Đang chuẩn bị không gian chat"
                    description="UIT AI đang nạp phiên trò chuyện, trạng thái người dùng và nguồn tham chiếu gần nhất."
                    size={240}
                />
            </Card>
        )
    }

    if (conversationsQuery.isError) {
        return (
            <Card className="mx-4 my-6 rounded-[2rem] border-white/70 bg-white/92 p-6 text-sm text-error-700 shadow-theme-sm dark:border-white/8 dark:bg-[#0f1728]/90 dark:text-error-300">
                {conversationsQuery.error.message}
            </Card>
        )
    }

    const displayRoleLabel = roleLabel || 'Sinh viên'
    const userName = session?.user.name ?? 'Tôi'
    const userDepartment = session?.user.department ?? 'UIT'
    const userEmail = session?.user.email ?? 'local@uit.edu.vn'
    const avatarInitials = session?.user.avatarInitials ?? 'UI'
    const composerReferenceMeta = composerContextReference ? getReferenceStatusMeta(composerContextReference.statusLabel) : null

    return (
        <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.09),transparent_24%),radial-gradient(circle_at_bottom_right,rgba(56,189,248,0.1),transparent_26%)]">
            <div className="absolute inset-0 surface-grid opacity-55 dark:opacity-30" />

            <Button
                variant="secondary"
                size="sm"
                aria-label={isHistoryOpen ? 'Thu gọn lịch sử' : 'Mở lịch sử'}
                aria-pressed={isHistoryOpen}
                onClick={toggleHistoryPanel}
                className="fixed left-4 top-4 z-50 h-12 w-12 rounded-[1.2rem] px-0 shadow-[0_20px_50px_rgba(15,23,42,0.12)]"
            >
                {isHistoryOpen ? <ChevronLeft size={18} /> : <Menu size={18} />}
            </Button>

            <AnimatePresence initial={false}>
                {isHistoryOpen ? (
                    <>
                        <motion.button
                            type="button"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setIsHistoryOpen(false)}
                            className="fixed inset-0 z-30 bg-slate-950/18 backdrop-blur-[2px] xl:hidden"
                            aria-label="Đóng lịch sử"
                        />

                        <motion.aside
                            initial={{ x: -28, opacity: 0 }}
                            animate={{ x: 0, opacity: 1 }}
                            exit={{ x: -28, opacity: 0 }}
                            transition={{ duration: 0.22, ease: 'easeOut' }}
                            className="fixed inset-y-0 left-0 z-40 flex w-[min(22rem,92vw)] flex-col border-r border-white/70 bg-white/92 shadow-[0_34px_120px_rgba(15,23,42,0.16)] backdrop-blur-2xl dark:border-white/10 dark:bg-[#08101d]/94 xl:w-[22rem]"
                        >
                            <HistorySidebarContent
                                canvasMode={canvasMode}
                                selectedConversationId={selectedConversation?.id}
                                conversationSearch={conversationSearch}
                                onConversationSearchChange={setConversationSearch}
                                conversationSections={conversationSections}
                                totalConversationCount={conversations.length}
                                clearPending={clearConversationsMutation.isPending}
                                deletePending={deleteConversationMutation.isPending}
                                onStartFreshChat={startFreshChat}
                                onClearConversations={() => void handleClearConversations()}
                                onOpenConversation={openHistoryConversation}
                                onDeleteConversation={(conversationId) => void handleDeleteConversation(conversationId)}
                                workspaceLinks={availableWorkspaceLinks}
                                activePath="/chat"
                                roleLabel={displayRoleLabel}
                                userName={userName}
                                userDepartment={userDepartment}
                                userEmail={userEmail}
                                avatarInitials={avatarInitials}
                                theme={theme}
                                onToggleTheme={toggleTheme}
                                logoutPending={logoutMutation.isPending}
                                onLogout={() => void handleLogout()}
                                onClose={() => setIsHistoryOpen(false)}
                            />
                        </motion.aside>
                    </>
                ) : null}
            </AnimatePresence>

            <div className={cn('relative z-10 flex min-h-screen flex-col transition-[padding-left] duration-300', isHistoryOpen ? SIDEBAR_WIDTH_CLASS : 'xl:pl-0')}>
                <div className="flex-1 overflow-hidden px-4 pt-20 md:px-8 xl:px-14">
                    <div className="mx-auto flex h-full max-w-[54rem] flex-col">
                        {showWelcomeCanvas ? (
                            <div className="flex flex-1 flex-col items-center justify-center gap-8 pb-12 text-center">
                                <div className="space-y-4">
                                    <BrandMark className="mx-auto h-20 w-20 rounded-[2rem] animate-soft-pulse" />
                                    <div className="space-y-3">
                                        <div className="text-[0.72rem] font-semibold uppercase tracking-[0.34em] text-brand-500">UIT Portal</div>
                                        <h1 className="text-4xl font-bold tracking-tight text-gray-950 dark:text-white md:text-5xl">UIT AI</h1>
                                        <p className="mx-auto max-w-2xl text-base leading-8 text-gray-500 dark:text-gray-300">
                                            Hỏi nhanh về học vụ, học phí, học bổng và tra cứu văn bản với nguồn tham chiếu gọn ngay trong từng câu trả lời.
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
                                                onClick={() => void sendMessage(prompt.label)}
                                                aria-label={prompt.label}
                                                disabled={isResponding}
                                                className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white/92 px-4 py-2.5 text-sm font-semibold text-gray-700 shadow-theme-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-200 hover:text-brand-700 hover:shadow-theme-sm disabled:cursor-not-allowed disabled:opacity-55 disabled:hover:translate-y-0 dark:border-gray-700 dark:bg-gray-900/92 dark:text-gray-200 dark:hover:border-brand-800 dark:hover:text-brand-200"
                                            >
                                                <Icon size={16} />
                                                {prompt.label}
                                            </button>
                                        )
                                    })}
                                </div>
                            </div>
                        ) : (
                            <div
                                ref={messagesViewportRef}
                                data-testid="chat-messages-viewport"
                                className="custom-scrollbar flex-1 overflow-y-auto pb-10"
                            >
                                <div className="space-y-6 pb-8">
                                    {displayedMessagesWithPreview.map((message) =>
                                        message.role === 'assistant' ? <AssistantMessage key={message.id} message={message} /> : <UserMessage key={message.id} message={message} />,
                                    )}

                                    {isResponding && !streamingAssistantMessage ? <TypingIndicator /> : null}
                                    <div ref={messageEndRef} />
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                <div className="border-t border-white/70 bg-white/84 px-4 py-4 backdrop-blur-xl dark:border-white/10 dark:bg-[#08111f]/84 md:px-6">
                    <div className="mx-auto max-w-[54rem]">
                        {mutationError ? (
                            <div className="mb-4 rounded-[1.4rem] border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-700 dark:border-error-900 dark:bg-error-950/40 dark:text-error-300">
                                {mutationError.message}
                            </div>
                        ) : null}

                        {generationNotice ? (
                            <p className="mb-3 px-1 text-sm text-gray-500 dark:text-gray-300">{generationNotice}</p>
                        ) : null}

                        <div className="rounded-[2rem] border border-white/80 bg-white/92 p-3 shadow-[0_20px_60px_rgba(15,23,42,0.1)] dark:border-white/10 dark:bg-[#0d1728]/92">
                            {composerContextReference ? (
                                <div className="mb-3 flex flex-wrap gap-2">
                                    <div
                                        className={cn(
                                            'inline-flex max-w-full items-center gap-2 rounded-full border px-3 py-2 text-xs shadow-theme-xs',
                                            composerReferenceMeta?.cardClassName,
                                        )}
                                    >
                                        <BookMarked size={14} />
                                        <span className="max-w-[18rem] truncate font-semibold">{composerContextReference.title}</span>
                                        <button
                                            type="button"
                                            onClick={() => setComposerContextReference(null)}
                                            className="inline-flex h-5 w-5 items-center justify-center rounded-full text-gray-500 transition-colors hover:bg-white/70 hover:text-gray-700 dark:text-gray-300 dark:hover:bg-white/10 dark:hover:text-white"
                                            aria-label={`Bỏ nguồn ${composerContextReference.title}`}
                                        >
                                            <X size={12} />
                                        </button>
                                    </div>
                                </div>
                            ) : null}

                            <label htmlFor="chat-draft" className="sr-only">
                                Hỏi UIT AI
                            </label>
                            <textarea
                                id="chat-draft"
                                ref={composerTextareaRef}
                                data-testid="chat-composer-input"
                                className="custom-scrollbar min-h-14 max-h-44 w-full resize-none border-0 bg-transparent px-3 py-2 text-base leading-7 text-gray-900 outline-none placeholder:text-gray-400 focus:ring-0 dark:text-white dark:placeholder:text-gray-500"
                                aria-label="Hỏi UIT AI"
                                value={draft}
                                onChange={(event) => {
                                    setDraft(event.target.value)
                                    if (generationNotice) {
                                        setGenerationNotice(null)
                                    }
                                }}
                                onKeyDown={(event) => {
                                    if (event.nativeEvent.isComposing) {
                                        return
                                    }

                                    if (event.key === 'Enter' && !event.shiftKey && !isResponding) {
                                        event.preventDefault()
                                        void sendDraftMessage()
                                    }
                                }}
                                placeholder="Nhập câu hỏi về học vụ, học phí, học bổng hoặc mã văn bản..."
                                rows={1}
                            />

                            <div className="mt-3 flex items-center justify-between gap-3 border-t border-white/70 px-1 pt-3 dark:border-white/10">
                                <div className="flex min-w-0 items-center gap-2">
                                    <RouteIntentLink
                                        to="/documents"
                                        aria-label="Mở thư viện tài liệu"
                                        className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-[1rem] border border-gray-200 bg-white/92 text-gray-500 transition-all duration-200 hover:border-brand-200 hover:text-brand-700 dark:border-gray-700 dark:bg-gray-900/92 dark:text-gray-300 dark:hover:border-brand-800 dark:hover:text-brand-200"
                                    >
                                        <Paperclip size={16} />
                                    </RouteIntentLink>

                                    <button
                                        type="button"
                                        aria-label={composerContextReference ? 'Bỏ nguồn đang ghim' : 'Ghim nguồn gần nhất cho câu hỏi tiếp theo'}
                                        onClick={toggleComposerContext}
                                        disabled={!canToggleComposerContext}
                                        className={cn(
                                            'inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-[1rem] border transition-all duration-200',
                                            canToggleComposerContext
                                                ? composerContextReference
                                                    ? 'border-brand-200 bg-brand-50 text-brand-700 dark:border-brand-800 dark:bg-brand-950/45 dark:text-brand-200'
                                                    : 'border-gray-200 bg-white/92 text-gray-500 hover:border-brand-200 hover:text-brand-700 dark:border-gray-700 dark:bg-gray-900/92 dark:text-gray-300 dark:hover:border-brand-800 dark:hover:text-brand-200'
                                                : 'cursor-not-allowed border-gray-200 bg-gray-100 text-gray-300 dark:border-gray-800 dark:bg-gray-900/70 dark:text-gray-600',
                                        )}
                                    >
                                        <BookMarked size={16} />
                                    </button>

                                    <p className="hidden truncate text-xs text-gray-500 dark:text-gray-400 sm:block">
                                        {composerContextReference
                                            ? `Đang ưu tiên ${getReferenceKindLabel(composerContextReference).toLowerCase()} cho câu hỏi tiếp theo.`
                                            : 'Ghim một nguồn gần nhất để câu trả lời bám sát tài liệu cụ thể.'}
                                    </p>
                                </div>

                                <Button
                                    size="sm"
                                    data-testid="chat-composer-send"
                                    className={cn(
                                        'h-11 w-11 shrink-0 rounded-[1rem] px-0 shadow-none transition-all duration-200',
                                        isResponding
                                            ? 'bg-slate-900 text-white hover:bg-slate-800 dark:bg-white dark:text-slate-900 dark:hover:bg-gray-100'
                                            : draft.trim()
                                              ? 'bg-brand-600 text-white hover:bg-brand-700'
                                              : 'bg-gray-200 text-gray-400 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-500 dark:hover:bg-gray-800',
                                    )}
                                    onClick={() => {
                                        if (isResponding) {
                                            stopGeneration()
                                            return
                                        }

                                        void sendDraftMessage()
                                    }}
                                    disabled={!isResponding && !draft.trim()}
                                    aria-label={isResponding ? 'Dừng tạo' : 'Gửi'}
                                >
                                    {isResponding ? <Square size={16} /> : <Send size={16} />}
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
