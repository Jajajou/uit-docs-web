import { useSearchParams } from 'react-router-dom'

export function useScenarioParam() {
    const [searchParams] = useSearchParams()
    return searchParams.get('scenario') ?? undefined
}
