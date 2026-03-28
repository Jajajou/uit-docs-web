import { apiClient } from '@/shared/api/client'
import { mapDocumentDtoToDocument } from '@/entities/documents/mappers'
import type { Document, DocumentDto } from '@/entities/documents/types'

export async function getDocuments(params?: { scenario?: string }): Promise<Document[]> {
    const response = await apiClient.get<{ documents: DocumentDto[] }>('/documents', {
        params,
    })

    return response.data.documents.map(mapDocumentDtoToDocument)
}

export async function getDocumentById(id: string, params?: { scenario?: string }): Promise<Document> {
    const response = await apiClient.get<{ document: DocumentDto }>(`/documents/${id}`, {
        params,
    })

    return mapDocumentDtoToDocument(response.data.document)
}

export async function archiveDocument(id: string, params?: { scenario?: string }): Promise<Document> {
    const response = await apiClient.post<{ document: DocumentDto }>(`/documents/${id}/archive`, undefined, {
        params,
    })

    return mapDocumentDtoToDocument(response.data.document)
}

export async function reindexDocument(id: string, params?: { scenario?: string }): Promise<Document> {
    const response = await apiClient.post<{ document: DocumentDto }>(`/documents/${id}/reindex`, undefined, {
        params,
    })

    return mapDocumentDtoToDocument(response.data.document)
}
