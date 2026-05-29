import type { ComponentPropsWithoutRef } from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '@/shared/lib/cn'

export const Drawer = DialogPrimitive.Root
export const DrawerTrigger = DialogPrimitive.Trigger
export const DrawerClose = DialogPrimitive.Close

export function DrawerTitle({ className, ...props }: ComponentPropsWithoutRef<typeof DialogPrimitive.Title>) {
    return <DialogPrimitive.Title className={cn('text-lg font-semibold text-gray-900 dark:text-white', className)} {...props} />
}

export function DrawerDescription({ className, ...props }: ComponentPropsWithoutRef<typeof DialogPrimitive.Description>) {
    return <DialogPrimitive.Description className={cn('text-sm text-gray-500 dark:text-gray-400', className)} {...props} />
}

export function DrawerContent({ className, children, ...props }: ComponentPropsWithoutRef<typeof DialogPrimitive.Content>) {
    return (
        <DialogPrimitive.Portal>
            <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" />
            <DialogPrimitive.Content
                className={cn(
                    'fixed right-0 top-0 z-50 flex h-screen w-[min(30rem,100vw)] flex-col border-l border-gray-200 bg-white p-6 shadow-theme-xl dark:border-gray-800 dark:bg-gray-950',
                    className,
                )}
                {...props}
            >
                <DialogPrimitive.Close className="absolute right-4 top-4 rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-800 dark:hover:text-gray-200">
                    <X size={16} />
                </DialogPrimitive.Close>
                {children}
            </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
    )
}
