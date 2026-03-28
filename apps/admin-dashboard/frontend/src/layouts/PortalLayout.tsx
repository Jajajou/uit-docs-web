import { portalNavItems } from '@/app/config/routes'
import { useRouteWarmup } from '@/app/router/useRouteWarmup'
import { AppShellFrame } from '@/features/navigation/AppShellFrame'

export default function PortalLayout() {
    useRouteWarmup('/portal/upload')

    return (
        <AppShellFrame
            shellKind="portal"
            sidebarTitle="Knowledge Portal"
            sidebarSubtitle="Internal"
            navItems={portalNavItems}
        />
    )
}
