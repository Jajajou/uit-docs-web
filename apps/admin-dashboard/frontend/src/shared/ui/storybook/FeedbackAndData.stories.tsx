import type { ReactNode } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Badge, Card, EmptyState, Skeleton, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow, Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/ui'
import { Inbox } from 'lucide-react'

const meta = {
    title: 'Foundation/Primitives/Feedback and Data',
    component: Card,
} satisfies Meta<typeof Card>

export default meta

type Story = StoryObj<typeof meta>

function Surface({ children, dark = false }: { children: ReactNode; dark?: boolean }) {
    return (
        <div className={dark ? 'dark' : undefined}>
            <div className={`rounded-3xl p-4 ${dark ? 'bg-gray-950' : 'bg-gray-50'}`}>{children}</div>
        </div>
    )
}

export const BadgeStates: Story = {
    render: () => (
        <Surface>
            <div className="flex flex-wrap gap-2">
                <Badge>Neutral</Badge>
                <Badge tone="brand">Brand</Badge>
                <Badge tone="success">Success</Badge>
                <Badge tone="warning">Warning</Badge>
                <Badge tone="danger">Danger</Badge>
            </div>
        </Surface>
    ),
}

export const CardAndLoadingStates: Story = {
    render: () => (
        <Surface>
            <div className="space-y-6">
                <Card className="space-y-3">
                    <div className="font-semibold text-gray-900 dark:text-white">Loading skeleton</div>
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-2/3" />
                </Card>

                <Card className="border-error-200 bg-error-50 text-error-700 dark:border-error-800 dark:bg-error-950 dark:text-error-200">
                    Upload failed because the content hash already exists.
                </Card>

                <Card className="p-0">
                    <Table>
                        <TableHead>
                            <TableRow>
                                <TableHeaderCell>Column A</TableHeaderCell>
                                <TableHeaderCell>Column B</TableHeaderCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            <TableRow>
                                <TableCell>Value 1</TableCell>
                                <TableCell>Value 2</TableCell>
                            </TableRow>
                        </TableBody>
                    </Table>
                </Card>
            </div>
        </Surface>
    ),
}

export const EmptyAndTabs: Story = {
    render: () => (
        <Surface>
            <div className="space-y-6">
                <Tabs defaultValue="one">
                    <TabsList>
                        <TabsTrigger value="one">One</TabsTrigger>
                        <TabsTrigger value="two">Two</TabsTrigger>
                    </TabsList>
                    <TabsContent value="one">
                        <Card>First tab content</Card>
                    </TabsContent>
                    <TabsContent value="two">
                        <Card>Second tab content</Card>
                    </TabsContent>
                </Tabs>

                <EmptyState icon={Inbox} title="No items" description="Empty states should be first-class in the foundation layer." />
            </div>
        </Surface>
    ),
}

export const DarkMode: Story = {
    render: () => (
        <Surface dark>
            <div className="space-y-4">
                <div className="flex gap-2">
                    <Badge>Neutral</Badge>
                    <Badge tone="success">Approved</Badge>
                    <Badge tone="warning">Needs review</Badge>
                </div>
                <Card className="space-y-2">
                    <div className="font-semibold text-gray-900 dark:text-white">Dark surface card</div>
                    <div className="text-sm text-gray-500">Shared feedback and data components keep readable contrast.</div>
                </Card>
            </div>
        </Surface>
    ),
}
