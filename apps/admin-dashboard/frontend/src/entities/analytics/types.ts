/**
 * Analytics entity types aligned with backend schemas.
 *
 * Maps to:
 *   - OverviewStats     -> /api/analytics/overview
 *   - PipelineStatus    -> /api/analytics/pipeline
 *   - GraphStats        -> /api/analytics/graph-stats
 *   - SystemHealth      -> /api/analytics/health
 */

/* ── Backend DTO shapes (snake_case) ── */

export interface OverviewStatsDto {
    total_documents: number
    indexed: number
    processing: number
    failed: number
    pending: number
    lightrag_health: string
}

export interface PipelineStatusDto {
    is_processing: boolean
    queue_size: number
    last_processed: string | null
    error_message: string | null
}

export interface GraphStatsDto {
    total_labels: number
    top_labels: string[]
}

export interface SystemHealthDto {
    admin_api: string
    lightrag: string
    lightrag_url: string // intentionally NOT exposed to UI
}

/* ── Frontend domain shapes (camelCase) ── */

export interface OverviewStats {
    totalDocuments: number
    indexed: number
    processing: number
    failed: number
    pending: number
    lightragHealth: string
}

export interface PipelineStatus {
    isProcessing: boolean
    queueSize: number
    lastProcessed: string | null
    errorMessage: string | null
}

export interface GraphStats {
    totalLabels: number
    topLabels: string[]
}

/**
 * Safe health shape for UI rendering.
 * `lightrag_url` is intentionally omitted to avoid leaking internal infrastructure details.
 */
export interface SystemHealth {
    adminApi: string
    lightrag: string
}

export type HealthBadge = 'healthy' | 'mock-backed' | 'down'
