import type { ComponentPropsWithoutRef } from 'react'
import * as TabsPrimitive from '@radix-ui/react-tabs'
import { cn } from '@/shared/lib/cn'

export const Tabs = TabsPrimitive.Root

export function TabsList({ className, ...props }: ComponentPropsWithoutRef<typeof TabsPrimitive.List>) {
    return (
        <TabsPrimitive.List
            className={cn('inline-flex rounded-xl bg-gray-100 p-1 dark:bg-gray-800', className)}
            {...props}
        />
    )
}

export function TabsTrigger({ className, ...props }: ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) {
    return (
        <TabsPrimitive.Trigger
            className={cn(
                'rounded-lg px-3 py-2 text-sm font-medium text-gray-600 transition data-[state=active]:bg-white data-[state=active]:text-gray-900 dark:text-gray-300 dark:data-[state=active]:bg-gray-900 dark:data-[state=active]:text-white',
                className,
            )}
            {...props}
        />
    )
}

export function TabsContent({ className, ...props }: ComponentPropsWithoutRef<typeof TabsPrimitive.Content>) {
    return <TabsPrimitive.Content className={cn('mt-4', className)} {...props} />
}
