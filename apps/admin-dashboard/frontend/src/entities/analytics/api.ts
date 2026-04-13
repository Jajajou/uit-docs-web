import { apiClient } from '@/shared/api/client'
import type {
    GraphStats,
    GraphStatsDto,
    OverviewStats,
    OverviewStatsDto,
    PipelineStatus,
    PipelineStatusDto,
    SystemHealth,
    SystemHealthDto,
} from '@/entities/analytics/types'

/* ── Mappers (snake_case DTO → camelCase domain) ── */

function mapOverviewStats(dto: OverviewStatsDto): OverviewStats {
    return {
        totalDocuments: dto.total_documents,
        indexed: dto.indexed,
        processing: dto.processing,
        failed: dto.failed,
        pending: dto.pending,
        lightragHealth: dto.lightrag_health,
    }
}

function mapPipelineStatus(dto: PipelineStatusDto): PipelineStatus {
    return {
        isProcessing: dto.is_processing,
        queueSize: dto.queue_size,
        lastProcessed: dto.last_processed,
        errorMessage: dto.error_message,
    }
}

function mapGraphStats(dto: GraphStatsDto): GraphStats {
    return {
        totalLabels: dto.total_labels,
        topLabels: dto.top_labels,
    }
}

function mapSystemHealth(dto: SystemHealthDto): SystemHealth {
    return {
        adminApi: dto.admin_api,
        lightrag: dto.lightrag,
        // lightrag_url intentionally omitted — not safe for portal UI
    }
}

/* ── API functions ── */

export async function getOverviewStats(): Promise<OverviewStats> {
    const response = await apiClient.get<OverviewStatsDto>('/analytics/overview')
    return mapOverviewStats(response.data)
}

export async function getPipelineStatus(): Promise<PipelineStatus> {
    const response = await apiClient.get<PipelineStatusDto>('/analytics/pipeline')
    return mapPipelineStatus(response.data)
}

export async function getGraphStats(): Promise<GraphStats> {
    const response = await apiClient.get<GraphStatsDto>('/analytics/graph-stats')
    return mapGraphStats(response.data)
}

export async function getSystemHealth(): Promise<SystemHealth> {
    const response = await apiClient.get<SystemHealthDto>('/analytics/health')
    return mapSystemHealth(response.data)
}
