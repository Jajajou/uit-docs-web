import type { ReactNode } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Button } from '@/shared/ui'

const meta = {
    title: 'Foundation/Primitives/Button',
    component: Button,
    args: {
        children: 'Primary action',
    },
} satisfies Meta<typeof Button>

export default meta

type Story = StoryObj<typeof meta>

function Surface({ children, dark = false, mobile = false }: { children: ReactNode; dark?: boolean; mobile?: boolean }) {
    return (
        <div className={dark ? 'dark' : undefined}>
            <div className={`rounded-3xl p-4 ${dark ? 'bg-gray-950' : 'bg-gray-50'} ${mobile ? 'max-w-sm' : ''}`}>{children}</div>
        </div>
    )
}

export const Default: Story = {
    render: () => (
        <Surface>
            <Button>Primary action</Button>
        </Surface>
    ),
}

export const Variants: Story = {
    render: () => (
        <Surface>
            <div className="flex flex-wrap gap-3">
                <Button>Primary</Button>
                <Button variant="secondary">Secondary</Button>
                <Button variant="ghost">Ghost</Button>
                <Button variant="outline">Outline</Button>
                <Button variant="danger">Danger</Button>
            </div>
        </Surface>
    ),
}

export const Loading: Story = {
    render: () => (
        <Surface>
            <Button isLoading>Saving role policy</Button>
        </Surface>
    ),
}

export const Disabled: Story = {
    render: () => (
        <Surface>
            <div className="flex flex-wrap gap-3">
                <Button disabled>Primary disabled</Button>
                <Button variant="secondary" disabled>
                    Secondary disabled
                </Button>
                <Button variant="danger" disabled>
                    Danger disabled
                </Button>
            </div>
        </Surface>
    ),
}

export const DarkMode: Story = {
    render: () => (
        <Surface dark>
            <div className="flex flex-wrap gap-3">
                <Button>Primary</Button>
                <Button variant="secondary">Secondary</Button>
                <Button variant="ghost">Ghost</Button>
                <Button variant="outline">Outline</Button>
            </div>
        </Surface>
    ),
}

export const MobileStack: Story = {
    render: () => (
        <Surface mobile>
            <div className="space-y-3">
                <Button fullWidth>Primary action</Button>
                <Button variant="secondary" fullWidth>
                    Secondary action
                </Button>
                <Button variant="outline" fullWidth>
                    Review metadata
                </Button>
            </div>
        </Surface>
    ),
}
