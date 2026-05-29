type Listener = (...args: unknown[]) => void

interface ListenerEntry {
    listener: Listener
    once: boolean
}

export class EventEmitter3 {
    private listeners = new Map<string | symbol, ListenerEntry[]>()

    on(event: string | symbol, listener: Listener) {
        return this.addListener(event, listener)
    }

    addListener(event: string | symbol, listener: Listener) {
        const existing = this.listeners.get(event) ?? []
        existing.push({ listener, once: false })
        this.listeners.set(event, existing)
        return this
    }

    once(event: string | symbol, listener: Listener) {
        const existing = this.listeners.get(event) ?? []
        existing.push({ listener, once: true })
        this.listeners.set(event, existing)
        return this
    }

    off(event: string | symbol, listener: Listener) {
        return this.removeListener(event, listener)
    }

    removeListener(event: string | symbol, listener: Listener) {
        const existing = this.listeners.get(event)
        if (!existing) {
            return this
        }

        const next = existing.filter((entry) => entry.listener !== listener)
        if (next.length > 0) {
            this.listeners.set(event, next)
        } else {
            this.listeners.delete(event)
        }

        return this
    }

    removeAllListeners(event?: string | symbol) {
        if (typeof event === 'undefined') {
            this.listeners.clear()
            return this
        }

        this.listeners.delete(event)
        return this
    }

    emit(event: string | symbol, ...args: unknown[]) {
        const existing = this.listeners.get(event)
        if (!existing?.length) {
            return false
        }

        for (const entry of [...existing]) {
            entry.listener(...args)
            if (entry.once) {
                this.removeListener(event, entry.listener)
            }
        }

        return true
    }

    listenerCount(event: string | symbol) {
        return this.listeners.get(event)?.length ?? 0
    }
}

export const EventEmitter = EventEmitter3
export default EventEmitter3
