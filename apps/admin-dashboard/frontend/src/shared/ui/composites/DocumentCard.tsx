import { RouteIntentLink } from '@/app/router/RouteIntentLink'
import { TemporalBadge, type TemporalState } from '../primitives/TemporalBadge'
import { cn } from '@/shared/lib/cn'

interface DocumentCardProps {
    id: string
    title: string
    href: string
    state: TemporalState
    delta?: string
    amendmentChain?: string
    className?: string
}

export function DocumentCard({ id, title, href, state, delta, amendmentChain, className }: DocumentCardProps) {
    const isSuperseded = state === 'superseded'

    return (
        <div
            className={cn(
                'group relative rounded-2xl border border-gray-200 bg-white p-4 shadow-sm transition hover:border-gray-300 hover:shadow-md dark:border-gray-800 dark:bg-gray-950 dark:hover:border-gray-700',
                className
            )}
        >
            <div className={cn('absolute left-0 top-0 bottom-0 w-1 rounded-l-2xl', {
                'bg-success-500 dark:bg-success-400': state === 'valid',
                'bg-warning-500 dark:bg-warning-400': state === 'expiring',
                'bg-gray-400 dark:bg-gray-600': state === 'superseded',
                'bg-purple-500 dark:bg-purple-400': state === 'amended',
            })} />

            <div className={cn('pl-2', isSuperseded && 'opacity-65')}>
                <div className={cn('font-mono text-xs font-semibold text-gray-900 dark:text-white mb-1 tracking-wide', isSuperseded && 'line-through opacity-70')}>
                    {id}
                </div>
                <RouteIntentLink
                    to={href}
                    className="block text-sm font-medium text-gray-700 hover:text-brand-600 dark:text-gray-300 dark:hover:text-brand-400 leading-snug mb-3"
                >
                    {title}
                </RouteIntentLink>

                <div className="flex items-center justify-between gap-3 mt-1">
                    <TemporalBadge state={state} />
                    {delta && <span className="font-mono text-[10px] text-gray-500 tracking-wider">{delta}</span>}
                </div>

                {amendmentChain && (
                    <div className="mt-3 pt-3 border-t border-dashed border-gray-200 dark:border-gray-800 font-mono text-[10px] text-purple-600 dark:text-purple-400 flex items-center gap-1.5">
                        ↳ {amendmentChain}
                    </div>
                )}
            </div>
        </div>
    )
}
