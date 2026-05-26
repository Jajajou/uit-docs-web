import axios from 'axios'
import { useSessionStore } from '@/entities/auth/store'
import { normalizeApiError } from '@/shared/api/error'
import { mockApiAdapter } from '@/shared/api/mockAdapter'
import { isMockAdapterEnabled } from '@/shared/api/mockRuntime'

function getApiBaseUrl() {
    const configuredBaseUrl = String(import.meta.env.VITE_API_BASE_URL ?? '').trim()
    return configuredBaseUrl || '/api'
}

export const apiClient = axios.create({
    baseURL: getApiBaseUrl(),
    timeout: 10000,
    withCredentials: true,
    adapter: isMockAdapterEnabled ? mockApiAdapter : undefined,
})

apiClient.interceptors.request.use((config) => {
    const requestId = crypto.randomUUID()
    const selectedRole = useSessionStore.getState().selectedRole

    config.headers.set('x-request-id', requestId)
    if (isMockAdapterEnabled) {
        config.headers.set('x-demo-role', selectedRole)
    }

    return config
})

apiClient.interceptors.response.use(
    (response) => response,
    (error) => Promise.reject(normalizeApiError(error)),
)
