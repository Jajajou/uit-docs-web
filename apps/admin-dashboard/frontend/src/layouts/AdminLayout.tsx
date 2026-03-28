import { adminNavItems } from '@/app/config/routes'
import { AppShellFrame } from '@/features/navigation/AppShellFrame'

export default function AdminLayout() {
    return (
        <AppShellFrame
            shellKind="admin"
            sidebarTitle="System Admin"
            sidebarSubtitle="Restricted"
            navItems={adminNavItems}
        />
    )
}
