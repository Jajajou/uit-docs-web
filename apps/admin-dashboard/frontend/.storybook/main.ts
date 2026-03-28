import path from 'path'
import { fileURLToPath } from 'url'
import type { StorybookConfig } from '@storybook/react-vite'

const currentDir = path.dirname(fileURLToPath(import.meta.url))

const config: StorybookConfig = {
    stories: ['../src/**/*.stories.@(ts|tsx)'],
    addons: ['@storybook/addon-essentials', '@storybook/addon-a11y'],
    framework: {
        name: '@storybook/react-vite',
        options: {},
    },
    viteFinal: async (config) => {
        config.resolve = config.resolve ?? {}
        config.resolve.alias = {
            ...(config.resolve.alias as Record<string, string>),
            '@': path.resolve(currentDir, '../src'),
        }

        return config
    },
}

export default config
