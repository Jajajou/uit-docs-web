import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { defineConfig, devices, type PlaywrightTestConfig } from '@playwright/test'

const frontendRoot = path.dirname(fileURLToPath(import.meta.url))
const backendRoot = path.resolve(frontendRoot, '../backend')

interface CreatePlaywrightConfigOptions {
    liveBackend: boolean
}

function resolveBackendPythonCommand() {
    if (process.env.WEB_BACKEND_PYTHON?.trim()) {
        return `"${process.env.WEB_BACKEND_PYTHON.trim()}"`
    }

    const candidates = [
        path.resolve(backendRoot, '..', '..', '..', '..', '..', 'anaconda3', 'python.exe'),
        'C:/Users/hoang/anaconda3/python.exe',
        'python',
    ]

    const resolved = candidates.find((candidate) => candidate === 'python' || fs.existsSync(candidate))
    return resolved === 'python' ? resolved : `"${resolved}"`
}

export function createPlaywrightConfig({ liveBackend }: CreatePlaywrightConfigOptions): PlaywrightTestConfig {
    const frontendEnv = {
        ...process.env,
        VITE_ENABLE_MOCKS: liveBackend ? 'false' : 'true',
    }
    const reuseExistingLocalServer = !process.env.CI && (liveBackend || process.env.PLAYWRIGHT_REUSE_SERVER === 'true')
    const frontendPort = liveBackend && !process.env.CI ? 3000 : 4173
    const frontendBaseUrl = `http://127.0.0.1:${frontendPort}`
    const reporters = process.env.CI
        ? [
              ['list'],
              [
                  'junit',
                  {
                      outputFile: path.join(frontendRoot, 'test-results', liveBackend ? 'playwright-live.xml' : 'playwright.xml'),
                  },
              ],
              [
                  'html',
                  {
                      outputFolder: path.join(frontendRoot, liveBackend ? 'playwright-report-live' : 'playwright-report'),
                      open: 'never',
                  },
              ],
          ]
        : [['list']]

    const webServer = [
        {
            command: `npm.cmd run dev -- --host 127.0.0.1 --port ${frontendPort}`,
            cwd: frontendRoot,
            env: frontendEnv,
            port: frontendPort,
            reuseExistingServer: reuseExistingLocalServer,
            timeout: 120_000,
        },
    ]

    if (liveBackend) {
        const backendPythonCommand = resolveBackendPythonCommand()
        webServer.push({
            command: `${backendPythonCommand} -m uvicorn api.main:app --host 127.0.0.1 --port 8001`,
            cwd: backendRoot,
            env: {
                ...process.env,
                ENABLE_DEMO_AUTH: 'true',
                TEST_MODE: 'true',
                SSO_PROVIDER_MODE: 'emulator',
                SSO_CALLBACK_BASE_URL: 'http://127.0.0.1:8001',
                SSO_FRONTEND_BASE_URL: frontendBaseUrl,
                CORS_ORIGINS: frontendBaseUrl,
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
        reporter: reporters,
        workers: liveBackend ? 1 : undefined,
        use: {
            baseURL: frontendBaseUrl,
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
