import { Badge } from './Badge'
import { cn } from '@/shared/lib/cn'

export type TemporalState = 'valid' | 'expiring' | 'superseded' | 'amended'

interface TemporalBadgeProps {
    state: TemporalState
    className?: string
}

export function TemporalBadge({ state, className }: TemporalBadgeProps) {
    const config: Record<TemporalState, { label: string; tone: 'success' | 'warning' | 'neutral' | 'purple'; dotClass: string }> = {
        valid: { label: 'Còn hiệu lực', tone: 'success', dotClass: 'bg-success-500 dark:bg-success-400' },
        expiring: { label: 'Sắp hết hạn', tone: 'warning', dotClass: 'bg-warning-500 dark:bg-warning-400' },
        superseded: { label: 'Đã thay thế', tone: 'neutral', dotClass: 'bg-gray-500 dark:bg-gray-400' },
        amended: { label: 'Đã sửa đổi', tone: 'purple', dotClass: 'bg-purple-500 dark:bg-purple-400' },
    }

    const { label, tone, dotClass } = config[state]

    return (
        <Badge tone={tone} className={cn('gap-1.5 font-medium tracking-wide shadow-sm border border-transparent', className)}>
            <span className={cn('h-1.5 w-1.5 rounded-full', dotClass)} />
            {label}
        </Badge>
    )
}
