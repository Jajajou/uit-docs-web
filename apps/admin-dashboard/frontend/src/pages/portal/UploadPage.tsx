import { motion } from 'framer-motion'
import { Upload } from 'lucide-react'
import { getExperienceRoleLabel } from '@/app/config/routes'
import { useSessionStore } from '@/entities/auth/store'
import { UploadWorkspace } from '@/features/uploads/UploadWorkspace'
import { useScenarioParam } from '@/shared/lib/scenario'
import { Badge } from '@/shared/ui'

export default function UploadPage() {
    const scenario = useScenarioParam()
    const selectedRole = useSessionStore((state) => state.selectedRole)
    const roleLabel = getExperienceRoleLabel(selectedRole)

    return (
        <div className="space-y-6">
            <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22, ease: 'easeOut' }}
                className="rounded-[2rem] border border-white/70 bg-white/88 px-6 py-6 shadow-theme-sm backdrop-blur-sm dark:border-white/8 dark:bg-[#1b2739]/88"
            >
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-2">
                        <div className="inline-flex items-center gap-2 text-sm font-semibold text-brand-600">
                            <Upload size={16} />
                            Tải tài liệu
                        </div>
                        <h1 className="text-2xl font-semibold text-gray-950 dark:text-white">Nạp tài liệu vào luồng duyệt nội bộ</h1>
                        <p className="max-w-3xl text-sm leading-6 text-gray-500">
                            Màn này chỉ giữ những trường thực sự cần cho teacher và admin: nguồn, tiêu đề, đơn vị ban hành, phạm vi hiển thị và ghi chú ngắn
                            cho người duyệt.
                        </p>
                    </div>
                    <Badge tone="brand">{roleLabel}</Badge>
                </div>
            </motion.div>

            <UploadWorkspace scenario={scenario} />
        </div>
    )
}
