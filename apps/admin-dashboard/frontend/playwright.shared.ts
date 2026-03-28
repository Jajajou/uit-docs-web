import path from 'path'
import { fileURLToPath } from 'url'
import { defineConfig, devices, type PlaywrightTestConfig } from '@playwright/test'

const frontendRoot = path.dirname(fileURLToPath(import.meta.url))
const backendRoot = path.resolve(frontendRoot, '../backend')

interface CreatePlaywrightConfigOptions {
    liveBackend: boolean
}

export function createPlaywrightConfig({ liveBackend }: CreatePlaywrightConfigOptions): PlaywrightTestConfig {
    const frontendEnv = {
        ...process.env,
        VITE_ENABLE_MOCKS: liveBackend ? 'false' : 'true',
    }
    const reuseExistingLocalServer = !process.env.CI && !liveBackend

    const webServer = [
        {
            command: 'npm.cmd run dev -- --host 127.0.0.1 --port 4173',
            cwd: frontendRoot,
            env: frontendEnv,
            port: 4173,
            reuseExistingServer: reuseExistingLocalServer,
            timeout: 120_000,
        },
    ]

    if (liveBackend) {
        webServer.push({
            command: 'python -m uvicorn api.main:app --host 127.0.0.1 --port 8001',
            cwd: backendRoot,
            env: {
                ...process.env,
            },
            port: 8001,
            reuseExistingServer: reuseExistingLocalServer,
            timeout: 120_000,
        })
    }

    return defineConfig({
        testDir: './e2e',
        timeout: 30_000,
        expect: {
            timeout: 5_000,
        },
        fullyParallel: !liveBackend,
        forbidOnly: Boolean(process.env.CI),
        retries: process.env.CI ? 1 : 0,
        reporter: [['list']],
        workers: liveBackend ? 1 : undefined,
        use: {
            baseURL: 'http://127.0.0.1:4173',
            trace: 'on-first-retry',
            screenshot: 'only-on-failure',
            video: 'retain-on-failure',
        },
        projects: [
            {
                name: 'chromium',
                use: { ...devices['Desktop Chrome'] },
            },
        ],
        testMatch: liveBackend ? '**/live-backend.spec.ts' : '**/*.spec.ts',
        testIgnore: liveBackend ? undefined : ['**/live-backend.spec.ts'],
        webServer,
    })
}
