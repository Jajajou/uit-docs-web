import type { ReactNode } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Bot, Home, Library, Upload } from 'lucide-react'
import { DataTable, FilterBar, MetadataPanel, PageHeader, Sidebar, Topbar } from '@/shared/ui'

const meta = {
    title: 'Foundation/Composites/Shell',
    component: PageHeader,
    args: {
        title: 'Composite foundation',
    },
} satisfies Meta<typeof PageHeader>

export default meta

type Story = StoryObj<typeof meta>

const navItems = [
    { label: 'Home', path: '/', icon: Home },
    { label: 'Upload', path: '/portal/upload', icon: Upload },
    { label: 'Library', path: '/portal/library', icon: Library },
]

interface TableRowSample {
    id: string
    title: string
    status: string
}

const tableRows: TableRowSample[] = [{ id: '1', title: 'Quy dinh hoc vu', status: 'approved' }]

function Surface({ children, dark = false, mobile = false }: { children: ReactNode; dark?: boolean; mobile?: boolean }) {
    return (
        <div className={dark ? 'dark' : undefined}>
            <div className={`rounded-3xl p-4 ${dark ? 'bg-gray-950' : 'bg-gray-50'} ${mobile ? 'max-w-sm' : ''}`}>{children}</div>
        </div>
    )
}

export const Gallery: Story = {
    args: {
        title: 'Composite foundation',
    },
    render: () => (
        <Surface>
            <div className="space-y-6">
                <PageHeader
                    title="Composite foundation"
                    description="Shell-level components used across public, portal and admin layouts."
                    icon={Bot}
                />

                <FilterBar searchValue="" onSearchChange={() => undefined} actions={<div className="text-sm text-gray-500">Actions slot</div>} />

                <MetadataPanel
                    title="Metadata panel"
                    entries={[
                        { label: 'Document type', value: 'regulation' },
                        { label: 'Confidence', value: '93%' },
                    ]}
                />

                <DataTable
                    rows={tableRows}
                    getRowKey={(row) => row.id}
                    columns={[
                        { key: 'title', header: 'Title', render: (row) => row.title },
                        { key: 'status', header: 'Status', render: (row) => row.status },
                    ]}
                    emptyIcon={Library}
                    emptyTitle="No rows"
                    emptyDescription="Used for library, jobs and submissions."
                />

                <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
                    <Sidebar title="Knowledge Portal" subtitle="Internal" items={navItems} />
                    <div className="space-y-4">
                        <Topbar
                            title="Library"
                            breadcrumbs={[{ label: 'PORTAL' }, { label: 'Library' }]}
                            roleSwitcher={<div className="rounded-xl border border-gray-200 px-3 py-2 text-sm">Role switcher slot</div>}
                        />
                    </div>
                </div>
            </div>
        </Surface>
    ),
}

export const DataTableStates: Story = {
    render: () => (
        <Surface>
            <div className="space-y-6">
                <DataTable
                    rows={tableRows}
                    getRowKey={(row) => row.id}
                    columns={[
                        { key: 'title', header: 'Title', render: (row) => row.title },
                        { key: 'status', header: 'Status', render: (row) => row.status },
                    ]}
                    emptyIcon={Library}
                    emptyTitle="No rows"
                    emptyDescription="Used for library, jobs and submissions."
                />
                <DataTable<TableRowSample>
                    rows={[]}
                    getRowKey={(row) => row.id}
                    columns={[
                        { key: 'title', header: 'Title', render: (row) => row.title },
                    ]}
                    emptyIcon={Library}
                    emptyTitle="No rows"
                    emptyDescription="Empty state coverage."
                />
                <DataTable<TableRowSample>
                    rows={[]}
                    isLoading
                    getRowKey={(row) => row.id}
                    columns={[
                        { key: 'title', header: 'Title', render: (row) => row.title },
                    ]}
                    emptyIcon={Library}
                    emptyTitle="No rows"
                    emptyDescription="Loading coverage."
                />
            </div>
        </Surface>
    ),
}

export const FilterAndMetadataStates: Story = {
    render: () => (
        <Surface dark>
            <div className="space-y-6">
                <FilterBar
                    searchValue="hoc phi"
                    onSearchChange={() => undefined}
                    searchPlaceholder="Search..."
                    actions={<div className="text-sm text-gray-500">Filter actions</div>}
                />
                <MetadataPanel
                    title="Metadata panel"
                    entries={[
                        { label: 'Reasoning', value: 'Detected from the official bulletin footer.' },
                        { label: 'Document number', value: '88/TB-UIT' },
                        { label: 'Academic year', value: '2025-2026', hint: 'Optional temporal field' },
                    ]}
                />
            </div>
        </Surface>
    ),
}

export const MobileShell: Story = {
    render: () => (
        <Surface mobile>
            <div className="space-y-4">
                <PageHeader title="Mobile library" description="Shared shell components in a narrow viewport." icon={Bot} />
                <FilterBar searchValue="" onSearchChange={() => undefined} />
                <MetadataPanel
                    title="Mobile metadata"
                    entries={[
                        { label: 'Visibility', value: 'public' },
                        { label: 'Version', value: '2' },
                    ]}
                />
            </div>
        </Surface>
    ),
}
