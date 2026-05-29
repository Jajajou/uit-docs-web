export function formatDate(date: string | null | undefined, options?: Intl.DateTimeFormatOptions) {
    if (!date) {
        return 'Not available'
    }

    return new Intl.DateTimeFormat('vi-VN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        ...options,
    }).format(new Date(date))
}

export function formatDateTime(date: string | null | undefined) {
    if (!date) {
        return 'Not available'
    }

    return new Intl.DateTimeFormat('vi-VN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    }).format(new Date(date))
}

export function formatPercent(value: number) {
    return `${Math.round(value * 100)}%`
}

export function formatFileSize(bytes: number) {
    if (bytes < 1024) {
        return `${bytes} B`
    }

    if (bytes < 1024 * 1024) {
        return `${(bytes / 1024).toFixed(1)} KB`
    }

    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
