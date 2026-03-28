export type MockScenario =
    | 'happy'
    | 'empty'
    | 'error'
    | 'auth-error'
    | 'duplicate-upload'
    | 'low-confidence'
    | 'archived-doc'
    | 'failed-job'
    | 'non-compliant-internal-email'
    | 'dense-audit-history'
    | 'forbidden'

export interface MockRequestDescriptor {
    method: string
    pathname: string
    params?: Record<string, unknown>
    data?: unknown
    headers?: Record<string, string>
    requestId: string
}

export interface MockHttpResponse<TData = unknown> {
    status: number
    data: TData
}

export interface MockHttpError {
    code: string
    message: string
    status: number
    details?: unknown
}
