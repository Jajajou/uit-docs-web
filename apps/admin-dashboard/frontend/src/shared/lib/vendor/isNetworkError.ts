const NETWORK_ERROR_PATTERNS = [
    'networkerror',
    'network request failed',
    'failed to fetch',
    'fetch failed',
    'load failed',
    'econnreset',
    'econnrefused',
    'enotfound',
    'etimedout',
    'socket hang up',
]

export default function isNetworkError(error: unknown): boolean {
    if (!(error instanceof Error)) {
        return false
    }

    const message = `${error.name} ${error.message}`.toLowerCase()
    return NETWORK_ERROR_PATTERNS.some((pattern) => message.includes(pattern))
}
