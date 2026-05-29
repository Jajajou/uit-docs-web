import { Link } from 'react-router-dom'
import { Activity, AlertTriangle, BarChart3, FileText, LayoutDashboard, Loader2, Server } from 'lucide-react'
import { Button, Card, PageHeader } from '@/shared/ui'
import {
    useOverviewStatsQuery,
    usePipelineStatusQuery,
    useSystemHealthQuery,
    deriveHealthBadge,
} from '@/entities/analytics/queries'
import type { HealthBadge } from '@/entities/analytics/types'

/* ── Health badge rendering ── */

const BADGE_CONFIG: Record<HealthBadge, { label: string; className: string }> = {
    healthy: { label: 'Healthy', className: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' },
    'mock-backed': { label: 'Mock-backed', className: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300' },
    down: { label: 'Down', className: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' },
}

function HealthBadgeLabel({ badge }: { badge: HealthBadge }) {
    const config = BADGE_CONFIG[badge]
    return (
        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${config.className}`}>
            {config.label}
        </span>
    )
}

/* ── Stat card ── */

function StatCard({ label, value, icon: Icon }: { label: string; value: string | number; icon: typeof FileText }) {
    return (
        <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white/60 px-4 py-3 dark:border-gray-700 dark:bg-gray-800/50">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
                <Icon className="h-5 w-5" />
            </div>
            <div className="min-w-0">
                <div className="text-2xl font-bold text-gray-900 dark:text-white">{value}</div>
                <div className="truncate text-xs text-gray-500 dark:text-gray-400">{label}</div>
            </div>
        </div>
    )
}

/* ── Loading / Error states ── */

function SectionLoading() {
    return (
        <div className="flex items-center gap-2 rounded-xl border border-gray-200 bg-white/60 px-4 py-6 text-sm text-gray-400 dark:border-gray-700 dark:bg-gray-800/50">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading analytics…
        </div>
    )
}

function SectionError({ message }: { message?: string }) {
    return (
        <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50/60 px-4 py-6 text-sm text-red-600 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
            <AlertTriangle className="h-4 w-4" />
            {message || 'Failed to load analytics data.'}
        </div>
    )
}

/* ── Main page ── */

export default function PortalOverviewPage() {
    const overview = useOverviewStatsQuery()
    const pipeline = usePipelineStatusQuery()
    const health = useSystemHealthQuery()

    const badge = deriveHealthBadge(health.data?.adminApi, health.data?.lightrag)

    return (
        <div className="space-y-6">
            <PageHeader
                title="Portal overview"
                description="Internal shell entry point for teacher intake and admin control workflows."
                icon={LayoutDashboard}
            />

            {/* ── System health ── */}
            <div className="flex items-center gap-3">
                <Server className="h-4 w-4 text-gray-400" />
                <span className="text-sm font-medium text-gray-600 dark:text-gray-300">System status</span>
                {health.isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                ) : health.isError ? (
                    <HealthBadgeLabel badge="down" />
                ) : (
                    <HealthBadgeLabel badge={badge} />
                )}
            </div>

            {/* ── Analytics summary ── */}
            {overview.isLoading ? (
                <SectionLoading />
            ) : overview.isError ? (
                <SectionError message="Could not load document overview." />
            ) : overview.data ? (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                    <StatCard label="Total documents" value={overview.data.totalDocuments} icon={FileText} />
                    <StatCard label="Indexed" value={overview.data.indexed} icon={BarChart3} />
                    <StatCard label="Processing" value={overview.data.processing} icon={Activity} />
                    <StatCard label="Failed" value={overview.data.failed} icon={AlertTriangle} />
                    <StatCard label="Pending" value={overview.data.pending} icon={Loader2} />
                </div>
            ) : null}

            {/* ── Pipeline status ── */}
            {pipeline.isLoading ? (
                <SectionLoading />
            ) : pipeline.isError ? (
                <SectionError message="Could not load pipeline status." />
            ) : pipeline.data ? (
                <Card className="space-y-2">
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">Pipeline</div>
                    <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-600 dark:text-gray-300">
                        <span>
                            Status:{' '}
                            <strong className={pipeline.data.isProcessing ? 'text-amber-600' : 'text-emerald-600'}>
                                {pipeline.data.isProcessing ? 'Processing' : 'Idle'}
                            </strong>
                        </span>
                        <span>Queue: <strong>{pipeline.data.queueSize}</strong></span>
                        {pipeline.data.lastProcessed && (
                            <span>Last processed: <strong>{pipeline.data.lastProcessed}</strong></span>
                        )}
                        {pipeline.data.errorMessage && (
                            <span className="text-red-600 dark:text-red-400">Error: {pipeline.data.errorMessage}</span>
                        )}
                    </div>
                </Card>
            ) : null}

            {/* ── Navigation cards ── */}
            <div className="grid gap-6 lg:grid-cols-3">
                <Card className="space-y-4">
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">Upload foundation</div>
                    <p className="text-sm text-gray-500">Schema-aware upload flow with core metadata, extraction diagnostics and supplemental metadata slots.</p>
                    <Button asChild variant="secondary">
                        <Link to="/portal/upload">Open upload</Link>
                    </Button>
                </Card>
                <Card className="space-y-4">
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">Submission tracking</div>
                    <p className="text-sm text-gray-500">Contributor-safe list of pending, approved and rejected submissions.</p>
                    <Button asChild variant="secondary">
                        <Link to="/portal/submissions">View submissions</Link>
                    </Button>
                </Card>
                <Card className="space-y-4">
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">Admin queue</div>
                    <p className="text-sm text-gray-500">Review queue, library and job monitor remain isolated behind role guard.</p>
                    <Button asChild variant="secondary">
                        <Link to="/portal/review">Open review queue</Link>
                    </Button>
                </Card>
            </div>
        </div>
    )
}
