import { CheckCircle2, Circle, Clock3, XCircle } from 'lucide-react'
import { cn } from '@/shared/lib/cn'

export interface StatusStep {
    id: string
    label: string
    description: string
    state: 'done' | 'current' | 'pending' | 'failed'
}

function StatusIcon({ state }: { state: StatusStep['state'] }) {
    if (state === 'done') {
        return <CheckCircle2 size={18} className="text-success-600" />
    }

    if (state === 'current') {
        return <Clock3 size={18} className="text-brand-600" />
    }

    if (state === 'failed') {
        return <XCircle size={18} className="text-error-600" />
    }

    return <Circle size={18} className="text-gray-400" />
}

export function StatusTimeline({ steps }: { steps: StatusStep[] }) {
    return (
        <div className="space-y-4">
            {steps.map((step, index) => (
                <div key={step.id} className="flex gap-3">
                    <div className="flex flex-col items-center">
                        <StatusIcon state={step.state} />
                        {index < steps.length - 1 ? <div className="mt-1 h-full w-px bg-gray-200 dark:bg-gray-800" /> : null}
                    </div>
                    <div className={cn('pb-4', index === steps.length - 1 && 'pb-0')}>
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">{step.label}</div>
                        <div className="text-sm text-gray-500">{step.description}</div>
                    </div>
                </div>
            ))}
        </div>
    )
}
