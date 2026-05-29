import type { AxiosAdapter, AxiosResponse } from 'axios'
import { resolveMockRequest } from '@/mocks/scenarios/router'

function parseData(data: unknown) {
    if (typeof data !== 'string') {
        return data
    }

    try {
        return JSON.parse(data)
    } catch {
        return data
    }
}

export const mockApiAdapter: AxiosAdapter = async (config) => {
    const requestId = String(config.headers?.['x-request-id'] ?? crypto.randomUUID())
    const pathname = new URL(config.url ?? '', 'http://localhost').pathname.replace('/api', '') || '/'
    const headers =
        typeof config.headers?.toJSON === 'function'
            ? (config.headers.toJSON() as Record<string, string>)
            : ((config.headers ?? {}) as Record<string, string>)

    const response = await resolveMockRequest({
        method: config.method ?? 'get',
        pathname,
        params: (config.params ?? {}) as Record<string, unknown>,
        data: parseData(config.data),
        headers,
        requestId,
    })

    const axiosResponse: AxiosResponse = {
        data: response.data,
        status: response.status,
        statusText: response.status >= 400 ? 'Error' : 'OK',
        headers: {
            'x-request-id': requestId,
        },
        config,
        request: undefined,
    }

    return axiosResponse
}
