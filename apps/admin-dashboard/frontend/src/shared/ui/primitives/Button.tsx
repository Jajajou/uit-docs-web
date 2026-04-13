import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { Slot } from '@radix-ui/react-slot'
import { Loader2 } from 'lucide-react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/shared/lib/cn'

const buttonVariants = cva(
    'inline-flex items-center justify-center gap-2 rounded-2xl border text-sm font-semibold transition-all duration-200 disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-500/20',
    {
        variants: {
            variant: {
                primary:
                    'border-brand-600 bg-brand-600 text-white shadow-theme-sm hover:-translate-y-0.5 hover:border-brand-700 hover:bg-brand-700 hover:shadow-theme-md',
                secondary:
                    'border-gray-200 bg-white/92 text-gray-900 shadow-theme-xs hover:-translate-y-0.5 hover:border-brand-200 hover:text-brand-700 hover:shadow-theme-sm dark:border-[#24486d] dark:bg-[#0d1e31]/92 dark:text-[#eff6ff] dark:hover:border-[#4aa3ff] dark:hover:bg-[#112845]',
                ghost:
                    'border-transparent bg-transparent text-gray-600 hover:bg-white/80 hover:text-gray-900 dark:text-[#d7e8ff] dark:hover:bg-[#10233a] dark:hover:text-white',
                outline:
                    'border-brand-200 bg-brand-50/80 text-brand-700 hover:-translate-y-0.5 hover:bg-brand-100 dark:border-[#2e5f93] dark:bg-[#0a2038]/72 dark:text-[#9fd7ff] dark:hover:bg-[#103154]',
                danger: 'border-error-600 bg-error-600 text-white hover:bg-error-700 hover:border-error-700',
            },
            size: {
                sm: 'h-10 px-3.5',
                md: 'h-11 px-4.5',
                lg: 'h-12 px-5.5',
            },
            fullWidth: {
                true: 'w-full',
                false: '',
            },
        },
        defaultVariants: {
            variant: 'primary',
            size: 'md',
            fullWidth: false,
        },
    },
)

export interface ButtonProps
    extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
    isLoading?: boolean
    asChild?: boolean
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant, size, fullWidth, isLoading = false, asChild = false, children, disabled, ...props }, ref) => {
        const Component = asChild ? Slot : 'button'
        const content = asChild ? children : (
            <>
                {isLoading ? <Loader2 size={16} className="animate-spin" /> : null}
                {children}
            </>
        )

        return (
            <Component
                ref={ref}
                className={cn(buttonVariants({ variant, size, fullWidth }), className)}
                disabled={disabled || isLoading}
                aria-busy={isLoading || undefined}
                {...props}
            >
                {content}
            </Component>
        )
    },
)

Button.displayName = 'Button'

export { Button }
