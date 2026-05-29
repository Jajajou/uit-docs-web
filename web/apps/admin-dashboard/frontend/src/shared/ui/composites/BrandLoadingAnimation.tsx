import type { HTMLAttributes } from 'react'
import { BrandMark } from '@/shared/ui/composites/BrandMark'
import { cn } from '@/shared/lib/cn'

type BrandLoadingAnimationProps = HTMLAttributes<HTMLDivElement> & {
    title?: string
    description?: string
    size?: number
    compact?: boolean
}

export function BrandLoadingAnimation({
    className,
    size = 300,
    compact = false,
    title,
    description,
    ...props
}: BrandLoadingAnimationProps) {
    const frameSize = compact ? Math.min(size, 180) : size
    const markSize = compact ? Math.round(frameSize * 0.36) : Math.round(frameSize * 0.32)

    return (
        <div
            className={cn(
                'flex w-full flex-col items-center justify-center',
                className,
            )}
            {...props}
        >
            <div
                className={cn(
                    'relative flex items-center justify-center overflow-hidden rounded-[2rem] border border-brand-100/70 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.98),rgba(239,246,255,0.86))] shadow-[0_20px_60px_rgba(37,99,235,0.12)] ring-1 ring-white/70 dark:border-[#27456a] dark:bg-[radial-gradient(circle_at_top,rgba(11,24,39,0.96),rgba(8,17,31,0.92))] dark:ring-white/6',
                    compact ? 'p-2.5' : 'p-3.5',
                )}
                style={{ width: frameSize, height: frameSize }}
                role="status"
                aria-live="polite"
            >
                <div className="pointer-events-none absolute inset-[8%] rounded-full bg-[radial-gradient(circle,rgba(59,130,246,0.18),transparent_68%)] blur-2xl dark:bg-[radial-gradient(circle,rgba(96,165,250,0.18),transparent_70%)]" />
                <div className="pointer-events-none absolute inset-0 rounded-[inherit] bg-[linear-gradient(145deg,rgba(255,255,255,0.46),transparent_36%,rgba(147,197,253,0.18))] dark:bg-[linear-gradient(145deg,rgba(255,255,255,0.04),transparent_36%,rgba(96,165,250,0.12))]" />
                <div className="pointer-events-none absolute inset-[15%] rounded-full border border-brand-200/80 border-dashed opacity-80 animate-spin dark:border-brand-300/45" style={{ animationDuration: '10s' }} />
                <div className="pointer-events-none absolute inset-[24%] rounded-full border border-brand-300/65 opacity-80 animate-soft-pulse dark:border-brand-200/35" />
                <div className="pointer-events-none absolute inset-[34%] rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.92),rgba(255,255,255,0.26)_72%,transparent)] dark:bg-[radial-gradient(circle,rgba(15,23,42,0.92),rgba(15,23,42,0.28)_72%,transparent)]" />
                <div className="relative z-[1] animate-subtle-slide-in">
                    <BrandMark className="rounded-[1.4rem] shadow-[0_18px_42px_rgba(37,99,235,0.16)]" style={{ width: markSize, height: markSize }} />
                </div>
            </div>

            {title || description ? (
                <div className={cn('mx-auto max-w-xl text-center', compact ? 'mt-3 space-y-1' : 'mt-5 space-y-2')}>
                    {title ? (
                        <div className={cn('font-semibold tracking-tight text-gray-900 dark:text-white', compact ? 'text-sm' : 'text-base')}>
                            {title}
                        </div>
                    ) : null}
                    {description ? (
                        <p className={cn('mx-auto text-gray-500 dark:text-gray-300', compact ? 'max-w-sm text-xs leading-5' : 'max-w-lg text-sm leading-6')}>
                            {description}
                        </p>
                    ) : null}
                </div>
            ) : null}
        </div>
    )
}
