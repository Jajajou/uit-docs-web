import type { ReactNode } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Checkbox, Input, Select, Textarea } from '@/shared/ui'

const meta = {
    title: 'Foundation/Primitives/Form Controls',
    component: Input,
} satisfies Meta<typeof Input>

export default meta

type Story = StoryObj<typeof meta>

const roleOptions = [
    { label: 'Student', value: 'student' },
    { label: 'Teacher', value: 'teacher' },
    { label: 'Admin', value: 'admin' },
]

function Surface({ children, dark = false, mobile = false }: { children: ReactNode; dark?: boolean; mobile?: boolean }) {
    return (
        <div className={dark ? 'dark' : undefined}>
            <div className={`rounded-3xl p-4 ${dark ? 'bg-gray-950' : 'bg-gray-50'} ${mobile ? 'max-w-sm' : 'max-w-2xl'}`}>{children}</div>
        </div>
    )
}

export const DefaultStates: Story = {
    render: () => (
        <Surface>
            <div className="grid gap-4">
                <Input label="Title" placeholder="Document title" hint="This field feeds the library and document detail page." />
                <Textarea label="Notes" placeholder="Internal notes..." />
                <Select label="Role" options={roleOptions} />
                <Checkbox label="Publish when approved" hint="Used in the upload flow." />
            </div>
        </Surface>
    ),
}

export const ErrorStates: Story = {
    render: () => (
        <Surface>
            <div className="grid gap-4">
                <Input label="Title" error="A clear title is required." />
                <Textarea label="Notes" error="Reviewer notes must explain the risk." />
                <Select label="Role" options={roleOptions} error="Choose an access role." />
                <Checkbox label="Confirm review checklist" hint="Checkbox controls do not render inline error text in the current design system." />
            </div>
        </Surface>
    ),
}

export const DisabledStates: Story = {
    render: () => (
        <Surface>
            <div className="grid gap-4">
                <Input label="Title" value="Quy dinh hoc vu 2024-2025" disabled readOnly />
                <Textarea label="Notes" value="Archived records cannot be edited." disabled readOnly />
                <Select label="Role" options={roleOptions} disabled value="teacher" />
                <Checkbox label="Publish when approved" disabled checked />
            </div>
        </Surface>
    ),
}

export const DarkMode: Story = {
    render: () => (
        <Surface dark>
            <div className="grid gap-4">
                <Input label="Title" placeholder="Document title" />
                <Textarea label="Notes" placeholder="Internal notes..." />
                <Select label="Role" options={roleOptions} value="teacher" />
                <Checkbox label="Publish when approved" hint="Dark surfaces keep the same focus treatment." />
            </div>
        </Surface>
    ),
}

export const MobileLayout: Story = {
    render: () => (
        <Surface mobile>
            <div className="grid gap-4">
                <Input label="Title" placeholder="Mobile title" />
                <Textarea label="Notes" placeholder="Short review note..." />
                <Select label="Visibility" options={[{ label: 'Internal', value: 'internal' }, { label: 'Public', value: 'public' }]} />
                <Checkbox label="I confirm this source is official." />
            </div>
        </Surface>
    ),
}
