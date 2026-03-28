import { Card, Skeleton } from '@/shared/ui'

export default function RouteLoadingFallback() {
    return (
        <div className="min-h-screen bg-gray-50 p-4 dark:bg-gray-950 md:p-6">
            <div className="mx-auto max-w-7xl space-y-6">
                <Skeleton className="h-14 w-64" />
                <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
                    <Card className="hidden h-[70vh] space-y-4 lg:block">
                        <Skeleton className="h-10 w-full" />
                        <Skeleton className="h-10 w-full" />
                        <Skeleton className="h-10 w-full" />
                        <Skeleton className="h-10 w-full" />
                    </Card>
                    <div className="space-y-6">
                        <Card className="space-y-4">
                            <Skeleton className="h-8 w-56" />
                            <Skeleton className="h-5 w-2/3" />
                        </Card>
                        <Card className="space-y-4">
                            <Skeleton className="h-40 w-full" />
                            <Skeleton className="h-40 w-full" />
                        </Card>
                    </div>
                </div>
            </div>
        </div>
    )
}
