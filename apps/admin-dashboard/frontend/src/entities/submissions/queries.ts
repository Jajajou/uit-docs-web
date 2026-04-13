import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createMultipartUploadSubmission, createUploadSubmission, getSubmissionById, getSubmissions } from '@/entities/submissions/api'
import type { FileUploadMutationPayload, UploadMutationPayload } from '@/entities/submissions/types'
import { isMockAdapterEnabled } from '@/shared/api/mockRuntime'

export function useSubmissionsQuery(params?: { scenario?: string }) {
    return useQuery({
        queryKey: ['submissions', params?.scenario ?? 'happy'],
        queryFn: () => getSubmissions(params),
    })
}

export function useSubmissionDetailQuery(id: string, params?: { scenario?: string }) {
    return useQuery({
        queryKey: ['submissions', id, params?.scenario ?? 'happy'],
        queryFn: () => getSubmissionById(id, params),
        enabled: Boolean(id),
    })
}

function useUploadMutation(
    endpoint: '/uploads/file' | '/uploads/text' | '/uploads/url',
    params?: { scenario?: string },
) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (payload: UploadMutationPayload) => createUploadSubmission(endpoint, payload, params),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['submissions'] })
            queryClient.invalidateQueries({ queryKey: ['jobs'] })
        },
    })
}

export function useFileUploadMutation(params?: { scenario?: string }) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ file, ...payload }: FileUploadMutationPayload) => {
            if (file && !isMockAdapterEnabled) {
                return createMultipartUploadSubmission(file, payload, params)
            }

            return createUploadSubmission('/uploads/file', payload, params)
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['submissions'] })
            queryClient.invalidateQueries({ queryKey: ['jobs'] })
        },
    })
}

export function useTextUploadMutation(params?: { scenario?: string }) {
    return useUploadMutation('/uploads/text', params)
}

export function useUrlUploadMutation(params?: { scenario?: string }) {
    return useUploadMutation('/uploads/url', params)
}
