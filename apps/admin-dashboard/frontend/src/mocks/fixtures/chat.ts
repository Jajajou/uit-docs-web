import type { ConversationDto, MessageDto } from '@/entities/chat/types'

const baseMessages: MessageDto[] = [
    {
        id: 'msg-001',
        role: 'user',
        content: 'Hoc phi hoc ky 2 nam nay bao nhieu?',
        created_at: '2026-03-20T03:00:00.000Z',
        references: [],
        warnings: [],
    },
    {
        id: 'msg-002',
        role: 'assistant',
        content: 'Hoc phi hien tai dang duoc tham chieu tu thong bao hoc phi hoc ky 2. Ban nen kiem tra lai theo khoa va so tin chi truoc khi nop.',
        created_at: '2026-03-20T03:00:05.000Z',
        confidence: 0.72,
        references: [
            {
                id: 'ref-001',
                title: 'Thong bao hoc phi hoc ky 2',
                href: '/documents/doc-002',
                excerpt: 'Thong bao muc hoc phi theo so tin chi va thoi han thanh toan.',
                status_label: 'Pending review',
            },
        ],
        warnings: [
            {
                code: 'low_confidence',
                message: 'Tai lieu nguon dang o trang thai pending review.',
            },
        ],
    },
]

export const conversationFixtures: ConversationDto[] = [
    {
        id: 'conv-001',
        title: 'Tra cuu hoc phi',
        updated_at: '2026-03-20T03:00:05.000Z',
        messages: baseMessages,
    },
    {
        id: 'conv-002',
        title: 'Dieu kien hoc bong',
        updated_at: '2026-03-19T06:15:00.000Z',
        messages: [
            {
                id: 'msg-003',
                role: 'user',
                content: 'Dieu kien hoc bong doanh nghiep la gi?',
                created_at: '2026-03-19T06:14:00.000Z',
                references: [],
                warnings: [],
            },
            {
                id: 'msg-004',
                role: 'assistant',
                content: 'Thong tin hoc bong cu da duoc luu tru. Ban nen lien he phong CTSV de nhan ban cap nhat moi nhat.',
                created_at: '2026-03-19T06:15:00.000Z',
                confidence: 0.41,
                references: [
                    {
                        id: 'ref-002',
                        title: 'Thong bao hoc bong doanh nghiep',
                        href: '/documents/doc-003',
                        excerpt: 'Thong bao cu da het hieu luc.',
                        status_label: 'Archived',
                    },
                ],
                warnings: [
                    {
                        code: 'archived_source',
                        message: 'Nguon tham chieu da duoc archive.',
                    },
                ],
            },
        ],
    },
    {
        id: 'conv-003',
        title: 'Lich dang ky mon hoc',
        updated_at: '2026-03-20T07:30:00.000Z',
        messages: [
            {
                id: 'msg-005',
                role: 'user',
                content: 'Lich dang ky mon hoc cho khoa 2024 bat dau khi nao?',
                created_at: '2026-03-20T07:29:00.000Z',
                references: [],
                warnings: [],
            },
            {
                id: 'msg-006',
                role: 'assistant',
                content: 'Theo thong bao da duoc duyet, lich dang ky mon hoc bat dau tu ngay 20/03/2026 va keo dai den 05/04/2026.',
                created_at: '2026-03-20T07:30:00.000Z',
                confidence: 0.9,
                references: [
                    {
                        id: 'ref-003',
                        title: 'Thong bao lich dang ky mon hoc',
                        href: '/documents/doc-004',
                        excerpt: 'Thong bao da duoc duyet va co the dung cho tra cuu sinh vien.',
                        status_label: 'Approved',
                    },
                ],
                warnings: [],
            },
        ],
    },
]
