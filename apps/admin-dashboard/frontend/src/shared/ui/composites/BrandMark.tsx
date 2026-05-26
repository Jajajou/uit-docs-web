import type { HTMLAttributes } from 'react'
import uitLogo from '@/assets/branding/uit-logo-official.png'
import { cn } from '@/shared/lib/cn'

type BrandMarkProps = HTMLAttributes<HTMLDivElement> & {
    label?: string
}

export function BrandMark({ className, label = 'UIT AI', ...props }: BrandMarkProps) {
    return (
        <div
            className={cn(
                'group relative isolate inline-flex items-center justify-center overflow-hidden rounded-[1.3rem] border border-brand-100/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(239,246,255,0.94))] p-2.5 shadow-[0_8px_24px_rgba(37,99,235,0.08)] ring-1 ring-white/72 dark:border-[#27456a] dark:bg-[linear-gradient(180deg,rgba(9,20,35,0.96),rgba(14,31,52,0.92))] dark:shadow-[0_10px_28px_rgba(8,15,32,0.26)] dark:ring-white/5',
                className,
            )}
            aria-label={label}
            {...props}
        >
            <span className="absolute inset-[16%] rounded-full bg-[radial-gradient(circle,rgba(59,130,246,0.12),rgba(191,219,254,0.03)_72%)] blur-xl dark:bg-[radial-gradient(circle,rgba(96,165,250,0.14),rgba(30,64,175,0.03)_72%)]" />
            <span className="absolute inset-0 rounded-[inherit] bg-[linear-gradient(135deg,rgba(147,197,253,0.14),transparent_38%,rgba(255,255,255,0.42)_68%,transparent)] opacity-65 dark:bg-[linear-gradient(135deg,rgba(59,130,246,0.12),transparent_38%,rgba(255,255,255,0.06)_70%,transparent)]" />
            <img
                src={uitLogo}
                alt={label}
                className="relative z-[1] h-full w-full object-contain drop-shadow-[0_4px_10px_rgba(8,47,73,0.1)] transition-transform duration-300 group-hover:scale-[1.01]"
            />
        </div>
    )
}
