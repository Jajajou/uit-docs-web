import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
    viteConfig,
    defineConfig({
        test: {
            coverage: {
                enabled: true,
                provider: 'v8',
                reporter: ['text', 'html', 'json-summary'],
                include: [
                    'src/app/config/routes.tsx',
                    'src/app/guards/RouteGuard.tsx',
                    'src/app/router/routeModules.ts',
                    'src/entities/**/*.ts',
                    'src/features/uploads/schema.ts',
                    'src/shared/api/*.ts',
                    'src/shared/lib/*.ts',
                ],
                exclude: [
                    '**/*.d.ts',
                    '**/*.stories.tsx',
                    '**/index.ts',
                    '**/types.ts',
                    '**/queries.ts',
                    'src/App.tsx',
                    'src/main.tsx',
                    'src/shared/lib/queryClient.js',
                ],
                thresholds: {
                    lines: 85,
                    functions: 85,
                    statements: 85,
                    branches: 75,
                },
            },
        },
    }),
)
