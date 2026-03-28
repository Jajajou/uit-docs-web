import type { ReactNode } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import {
    Button,
    Dialog,
    DialogContent,
    DialogDescription,
    DialogTitle,
    DialogTrigger,
    Drawer,
    DrawerContent,
    DrawerDescription,
    DrawerTitle,
    DrawerTrigger,
    FileDropzone,
    MetadataField,
    StatusTimeline,
} from '@/shared/ui'

const meta = {
    title: 'Foundation/Primitives/Overlays and Domain',
    component: FileDropzone,
    args: {
        value: [],
        onChange: () => undefined,
    },
} satisfies Meta<typeof FileDropzone>

export default meta

type Story = StoryObj<typeof meta>

function Surface({ children, dark = false, mobile = false }: { children: ReactNode; dark?: boolean; mobile?: boolean }) {
    return (
        <div className={dark ? 'dark' : undefined}>
            <div className={`rounded-3xl p-4 ${dark ? 'bg-gray-950' : 'bg-gray-50'} ${mobile ? 'max-w-sm' : ''}`}>{children}</div>
        </div>
    )
}

export const Gallery: Story = {
    args: {
        value: [],
        onChange: () => undefined,
    },
    render: () => (
        <Surface>
            <div className="space-y-6">
                <div className="grid gap-4 lg:grid-cols-2">
                    <Dialog>
                        <DialogTrigger asChild>
                            <Button>Open dialog</Button>
                        </DialogTrigger>
                        <DialogContent>
                            <div className="space-y-2">
                                <DialogTitle>Dialog</DialogTitle>
                                <DialogDescription>Confirmation flows use this shared dialog wrapper.</DialogDescription>
                            </div>
                        </DialogContent>
                    </Dialog>

                    <Drawer>
                        <DrawerTrigger asChild>
                            <Button variant="secondary">Open drawer</Button>
                        </DrawerTrigger>
                        <DrawerContent>
                            <div className="space-y-2">
                                <DrawerTitle>Drawer</DrawerTitle>
                                <DrawerDescription>Side panels like metadata inspectors can reuse this shell.</DrawerDescription>
                            </div>
                        </DrawerContent>
                    </Drawer>
                </div>

                <FileDropzone value={[]} onChange={() => undefined} />

                <div className="grid gap-4 lg:grid-cols-2">
                    <MetadataField label="Confidence" value="86%" hint="Example metadata card" />
                    <MetadataField label="Reasoning" value="Detected from valid date section." />
                </div>
            </div>
        </Surface>
    ),
}

export const TimelineStates: Story = {
    render: () => (
        <Surface>
            <StatusTimeline
                steps={[
                    { id: '1', label: 'Uploaded', description: 'File was received.', state: 'done' },
                    { id: '2', label: 'Extracting metadata', description: 'Temporal inference running.', state: 'current' },
                    { id: '3', label: 'Review rejected', description: 'Reviewer found missing issue number.', state: 'failed' },
                    { id: '4', label: 'Resubmission', description: 'Waiting for a corrected source.', state: 'pending' },
                ]}
            />
        </Surface>
    ),
}

export const MobileDropzone: Story = {
    args: {
        value: [],
        onChange: () => undefined,
    },
    render: () => (
        <Surface mobile>
            <FileDropzone value={[]} onChange={() => undefined} />
        </Surface>
    ),
}
