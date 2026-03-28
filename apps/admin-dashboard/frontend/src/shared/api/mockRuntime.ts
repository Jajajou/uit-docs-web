const shouldForceMockAdapter = import.meta.env.VITE_ENABLE_MOCKS === 'true'
const shouldUseTestAdapter = import.meta.env.MODE === 'test'

export const isMockAdapterEnabled = shouldForceMockAdapter || shouldUseTestAdapter

export const mockRuntimeMode = isMockAdapterEnabled ? 'adapter' : 'live'
