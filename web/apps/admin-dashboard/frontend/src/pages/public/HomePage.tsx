import { Link } from 'react-router-dom'
import { Bot, FileSearch, Upload } from 'lucide-react'
import { Button, Card, PageHeader } from '@/shared/ui'

export default function HomePage() {
    return (
        <div className="space-y-8">
            <PageHeader
                title="UIT AI"
                description="Không gian tra cứu của UIT AI với chat tham chiếu, nguồn tài liệu và kiểm soát vai trò rõ ràng."
                icon={Bot}
                actions={
                    <>
                        <Button asChild>
                            <Link to="/chat">Mở chat</Link>
                        </Button>
                        <Button asChild variant="secondary">
                            <Link to="/auth/login">Đăng nhập</Link>
                        </Button>
                    </>
                }
            />

            <div className="grid gap-6 lg:grid-cols-3">
                <Card className="space-y-3">
                    <Bot className="text-brand-600" />
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">Chat tham chiếu</div>
                    <p className="text-sm text-gray-500">Tra cứu nhanh với cảnh báo, độ tin cậy và liên kết tới nguồn tài liệu liên quan.</p>
                </Card>
                <Card className="space-y-3">
                    <FileSearch className="text-brand-600" />
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">Nguồn tài liệu</div>
                    <p className="text-sm text-gray-500">Trang chi tiết chỉ giữ các thông tin đủ để đọc, trích dẫn và kiểm tra hiệu lực của tài liệu.</p>
                </Card>
                <Card className="space-y-3">
                    <Upload className="text-brand-600" />
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">Không gian nội bộ</div>
                    <p className="text-sm text-gray-500">Giảng viên và quản trị viên có luồng tải tài liệu, kiểm soát hệ thống và phân quyền riêng.</p>
                </Card>
            </div>
        </div>
    )
}
