import axios, { AxiosError } from 'axios'

export interface ApiError {
    code: string
    message: string
    status: number
    requestId?: string
    details?: unknown
}

export class ApiClientError extends Error implements ApiError {
    code: string
    status: number
    requestId?: string
    details?: unknown

    constructor(error: ApiError) {
        super(error.message)
        this.name = 'ApiClientError'
        this.code = error.code
        this.status = error.status
        this.requestId = error.requestId
        this.details = error.details
    }
}

export function normalizeApiError(error: unknown): ApiClientError {
    if (error instanceof ApiClientError) {
        return error
    }

    if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError<{ error?: ApiError }>
        const apiError = axiosError.response?.data?.error

        return new ApiClientError({
            code: apiError?.code ?? 'unknown_error',
            message: apiError?.message ?? axiosError.message,
            status: axiosError.response?.status ?? 500,
            requestId: apiError?.requestId ?? axiosError.response?.headers?.['x-request-id'],
            details: apiError?.details,
        })
    }

    if (error instanceof Error) {
        return new ApiClientError({
            code: 'unexpected_error',
            message: error.message,
            status: 500,
        })
    }

    return new ApiClientError({
        code: 'unknown_error',
        message: 'An unknown error occurred',
        status: 500,
    })
}
