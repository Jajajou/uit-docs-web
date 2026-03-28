import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { Slot } from '@radix-ui/react-slot'
import { Loader2 } from 'lucide-react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/shared/lib/cn'

const buttonVariants = cva(
    'inline-flex items-center justify-center gap-2 rounded-xl border text-sm font-semibold transition-colors disabled:pointer-events-none disabled:opacity-50',
    {
        variants: {
            variant: {
                primary: 'border-brand-600 bg-brand-600 text-white hover:bg-brand-700 hover:border-brand-700',
                secondary: 'border-gray-200 bg-white text-gray-900 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-white dark:hover:bg-gray-800',
                ghost: 'border-transparent bg-transparent text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-800',
                outline: 'border-brand-200 bg-brand-50 text-brand-700 hover:bg-brand-100 dark:border-brand-800 dark:bg-brand-950 dark:text-brand-200 dark:hover:bg-brand-900',
                danger: 'border-error-600 bg-error-600 text-white hover:bg-error-700 hover:border-error-700',
            },
            size: {
                sm: 'h-9 px-3',
                md: 'h-11 px-4',
                lg: 'h-12 px-5',
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
