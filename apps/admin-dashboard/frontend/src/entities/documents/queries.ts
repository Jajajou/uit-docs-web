import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { archiveDocument, getDocumentById, getDocuments, reindexDocument } from '@/entities/documents/api'
import type { Document } from '@/entities/documents/types'

export function useDocumentsQuery(params?: { scenario?: string }) {
    return useQuery({
        queryKey: ['documents', params?.scenario ?? 'happy'],
        queryFn: () => getDocuments(params),
    })
}

export function useDocumentDetailQuery(id: string, params?: { scenario?: string }) {
    return useQuery({
        queryKey: ['documents', id, params?.scenario ?? 'happy'],
        queryFn: () => getDocumentById(id, params),
        enabled: Boolean(id),
    })
}

function updateDocumentCollection(current: Document[] | undefined, updatedDocument: Document) {
    return (current ?? []).map((entry) => (entry.id === updatedDocument.id ? updatedDocument : entry))
}

export function useArchiveDocumentMutation(params?: { scenario?: string }) {
    const queryClient = useQueryClient()
    const scenarioKey = params?.scenario ?? 'happy'

    return useMutation({
        mutationFn: (id: string) => archiveDocument(id, params),
        onSuccess: (document) => {
            queryClient.setQueryData(['documents', scenarioKey], (current: Document[] | undefined) =>
                updateDocumentCollection(current, document),
            )
            queryClient.setQueryData(['documents', document.id, scenarioKey], document)
            queryClient.invalidateQueries({ queryKey: ['audit-logs'] })
        },
    })
}

export function useReindexDocumentMutation(params?: { scenario?: string }) {
    const queryClient = useQueryClient()
    const scenarioKey = params?.scenario ?? 'happy'

    return useMutation({
        mutationFn: (id: string) => reindexDocument(id, params),
        onSuccess: (document) => {
            queryClient.setQueryData(['documents', scenarioKey], (current: Document[] | undefined) =>
                updateDocumentCollection(current, document),
            )
            queryClient.setQueryData(['documents', document.id, scenarioKey], document)
            queryClient.invalidateQueries({ queryKey: ['jobs'] })
            queryClient.invalidateQueries({ queryKey: ['audit-logs'] })
        },
    })
}
