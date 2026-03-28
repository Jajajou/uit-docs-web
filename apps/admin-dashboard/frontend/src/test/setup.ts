import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { resetMockScenarioState } from '@/mocks/scenarios/router'

afterEach(() => {
    resetMockScenarioState()
})
