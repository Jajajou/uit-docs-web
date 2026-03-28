import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

function createManualChunks(id: string) {
    const normalizedId = id.replace(/\\/g, '/')

    if (
        normalizedId.includes('/src/app/config/routes.tsx') ||
        normalizedId.includes('/src/app/router/RouteIntentLink.tsx') ||
        normalizedId.includes('/src/app/router/routePrefetch.ts') ||
        normalizedId.includes('/src/app/router/useRouteWarmup.ts') ||
        normalizedId.includes('/src/features/auth/RoleSwitcher.tsx') ||
        normalizedId.includes('/src/features/navigation/AppShellFrame.tsx') ||
        normalizedId.includes('/src/shared/ui/composites/Sidebar.tsx') ||
        normalizedId.includes('/src/shared/ui/composites/Topbar.tsx')
    ) {
        return 'shell-core'
    }

    if (
        normalizedId.includes('/src/shared/lib/format.ts') ||
        normalizedId.includes('/src/shared/ui/composites/DataTable.tsx') ||
        normalizedId.includes('/src/shared/ui/composites/MetadataPanel.tsx') ||
        normalizedId.includes('/src/shared/ui/composites/PageHeader.tsx') ||
        normalizedId.includes('/src/shared/ui/primitives/Badge.tsx') ||
        normalizedId.includes('/src/shared/ui/primitives/EmptyState.tsx')
    ) {
        return 'feature-ui'
    }

    if (!normalizedId.includes('/node_modules/')) {
        return undefined
    }

    if (
        normalizedId.includes('/react/') ||
        normalizedId.includes('/react-dom/') ||
        normalizedId.includes('react-router-dom') ||
        normalizedId.includes('@remix-run/router') ||
        normalizedId.includes('/scheduler/')
    ) {
        return 'framework-vendor'
    }

    if (normalizedId.includes('@tanstack/react-query') || normalizedId.includes('axios') || normalizedId.includes('zustand'))
        return 'data-vendor'
    if (normalizedId.includes('react-hook-form') || normalizedId.includes('zod') || normalizedId.includes('react-dropzone'))
        return 'form-vendor'
    if (normalizedId.includes('lucide-react')) return 'icon-vendor'

    if (
        normalizedId.includes('@radix-ui') ||
        normalizedId.includes('framer-motion') ||
        normalizedId.includes('sonner') ||
        normalizedId.includes('class-variance-authority') ||
        normalizedId.includes('tailwind-merge') ||
        normalizedId.includes('clsx')
    ) {
        return 'ui-vendor'
    }

    return 'vendor'
}

export default defineConfig({
    plugins: [react(), tailwindcss()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        port: 3000,
        proxy: {
            '/api': {
                target: 'http://localhost:8001',
                changeOrigin: true,
            },
        },
    },
    build: {
        rollupOptions: {
            output: {
                manualChunks: createManualChunks,
            },
        },
    },
    test: {
        environment: 'jsdom',
        setupFiles: './src/test/setup.ts',
        globals: true,
        exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
    },
})
