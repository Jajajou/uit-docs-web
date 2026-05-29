import { useQuery } from '@tanstack/react-query'
import { getOverviewStats, getPipelineStatus, getGraphStats, getSystemHealth } from '@/entities/analytics/api'
import type { HealthBadge } from '@/entities/analytics/types'

const ANALYTICS_STALE_TIME = 30_000 // 30 seconds — analytics data is not time-critical

export function useOverviewStatsQuery() {
    return useQuery({
        queryKey: ['analytics', 'overview'],
        queryFn: getOverviewStats,
        staleTime: ANALYTICS_STALE_TIME,
    })
}

export function usePipelineStatusQuery() {
    return useQuery({
        queryKey: ['analytics', 'pipeline'],
        queryFn: getPipelineStatus,
        staleTime: ANALYTICS_STALE_TIME,
    })
}

export function useGraphStatsQuery() {
    return useQuery({
        queryKey: ['analytics', 'graph-stats'],
        queryFn: getGraphStats,
        staleTime: ANALYTICS_STALE_TIME,
    })
}

export function useSystemHealthQuery() {
    return useQuery({
        queryKey: ['analytics', 'health'],
        queryFn: getSystemHealth,
        staleTime: ANALYTICS_STALE_TIME,
    })
}

/**
 * Derive a safe health badge label from the raw health strings.
 * This avoids exposing internal URL details to the UI.
 */
export function deriveHealthBadge(adminApi: string | undefined, lightrag: string | undefined): HealthBadge {
    if (!adminApi || !lightrag) return 'down'
    const adminOk = adminApi.toLowerCase().includes('ok') || adminApi.toLowerCase().includes('healthy')
    const lightragOk = lightrag.toLowerCase().includes('ok') || lightrag.toLowerCase().includes('healthy')
    if (adminOk && lightragOk) return 'healthy'
    if (adminOk && lightrag.toLowerCase().includes('mock')) return 'mock-backed'
    return 'down'
}
