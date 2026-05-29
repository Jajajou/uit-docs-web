import { BrandLoadingAnimation, Card } from '@/shared/ui'

export default function RouteLoadingFallback() {
    return (
        <div className="min-h-screen bg-gray-50 p-4 dark:bg-gray-950 md:p-6">
            <div className="mx-auto flex min-h-[80vh] max-w-5xl items-center justify-center">
                <Card className="w-full max-w-2xl border-white/70 bg-white/92 px-8 py-10 shadow-theme-lg backdrop-blur-sm dark:border-white/8 dark:bg-[#0f1728]/90">
                    <BrandLoadingAnimation
                        title="Đang mở không gian làm việc UIT AI"
                        description="Hệ thống đang nạp phiên, quyền truy cập và dữ liệu gần nhất để bạn tiếp tục thao tác."
                        size={240}
                    />
                </Card>
            </div>
        </div>
    )
}
