import { motion } from 'framer-motion'
import { Activity, ShieldCheck, Users } from 'lucide-react'
import { AdminUsersPanel } from '@/features/admin/AdminUsersPanel'
import { useScenarioParam } from '@/shared/lib/scenario'
import { Badge, Card } from '@/shared/ui'

const healthCards = [
    {
        label: 'Tài khoản được quản lý',
        value: '24',
        detail: 'Bao gồm giảng viên và quản trị viên đã được cấp quyền.',
        icon: Users,
    },
    {
        label: 'Hồ sơ chờ duyệt',
        value: '14',
        detail: 'Tài liệu mới đang chờ admin rà soát trước khi công bố.',
        icon: Activity,
    },
    {
        label: 'Tín hiệu hệ thống',
        value: 'Ổn định',
        detail: 'Chưa phát hiện lỗi nghiêm trọng trong lượt mô phỏng hiện tại.',
        icon: ShieldCheck,
    },
]

export default function ManagerPage() {
    const scenario = useScenarioParam()

    return (
        <div className="space-y-6">
            <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22, ease: 'easeOut' }}
                className="relative overflow-hidden rounded-[2rem] border border-white/70 bg-white/88 px-6 py-6 shadow-theme-sm backdrop-blur-sm dark:border-brand-400/16 dark:bg-[linear-gradient(180deg,rgba(6,14,26,0.94),rgba(10,24,42,0.96))] dark:shadow-[0_26px_70px_rgba(2,8,23,0.46)]"
            >
                <div className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-brand-300/70 to-transparent dark:via-brand-300/50" />
                <div className="pointer-events-none absolute -right-20 -top-16 h-48 w-48 rounded-full bg-brand-400/18 blur-3xl dark:bg-brand-300/12" />
                <div className="pointer-events-none absolute -left-16 bottom-0 h-32 w-32 rounded-full bg-sky-400/12 blur-3xl dark:bg-sky-300/10" />
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-2">
                        <div className="inline-flex items-center gap-2 text-sm font-semibold text-brand-600 dark:text-brand-200">
                            <ShieldCheck size={16} />
                            Quản trị hệ thống
                        </div>
                        <h1 className="text-2xl font-semibold text-gray-950 dark:text-white">Phân quyền người dùng và kiểm soát nội bộ</h1>
                        <p className="max-w-3xl text-sm leading-6 text-gray-500 dark:text-slate-300">
                            Dashboard này tập trung vào việc admin thực sự cần làm: xem sức khỏe hệ thống, rà tài khoản và gán lại role cho người dùng sau khi họ
                            đăng nhập bằng Google Workspace UIT.
                        </p>
                    </div>
                    <Badge tone="brand">Admin</Badge>
                </div>
            </motion.div>

            <section className="grid gap-4 lg:grid-cols-3">
                {healthCards.map((card, index) => {
                    const Icon = card.icon

                    return (
                        <motion.div
                            key={card.label}
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.22, ease: 'easeOut', delay: index * 0.04 }}
                        >
                            <Card className="relative overflow-hidden space-y-3 border-white/75 dark:border-brand-400/12 dark:bg-[linear-gradient(180deg,rgba(8,18,31,0.94),rgba(12,24,41,0.96))]">
                                <div className="pointer-events-none absolute inset-x-5 top-0 h-px bg-gradient-to-r from-transparent via-brand-300/60 to-transparent dark:via-brand-300/35" />
                                <div className="flex items-center gap-3">
                                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-50 text-brand-700 dark:bg-[linear-gradient(180deg,rgba(24,54,104,0.88),rgba(16,34,66,0.92))] dark:text-brand-100 dark:shadow-[0_0_0_1px_rgba(96,165,250,0.14)]">
                                        <Icon size={18} />
                                    </div>
                                    <div className="text-sm font-semibold text-gray-900 dark:text-white">{card.label}</div>
                                </div>
                                <div className="text-3xl font-semibold text-gray-950 dark:text-white">{card.value}</div>
                                <div className="text-sm leading-6 text-gray-500 dark:text-slate-300">{card.detail}</div>
                            </Card>
                        </motion.div>
                    )
                })}
            </section>

            <div className="space-y-4">
                <div className="space-y-2">
                    <h2 className="text-xl font-semibold text-gray-950 dark:text-white">Bảng phân quyền người dùng</h2>
                    <p className="text-sm leading-6 text-gray-500 dark:text-slate-300">
                        Sau khi tài khoản Google đăng nhập lần đầu, hệ thống giữ role student. Admin dùng bảng dưới để nâng quyền lên teacher hoặc admin, đồng
                        thời khóa hoặc mời lại tài khoản khi cần.
                    </p>
                </div>
                <AdminUsersPanel scenario={scenario} />
            </div>
        </div>
    )
}
