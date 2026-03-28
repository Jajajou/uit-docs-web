import { useEffect, useMemo, useState } from 'react'
import { Settings2 } from 'lucide-react'
import { toast } from 'sonner'
import { formatSettingGroup, maskSettingValue } from '@/entities/admin/presentation'
import { useSystemSettingPatchMutation, useSystemSettingsQuery } from '@/entities/admin/queries'
import type { SystemSetting } from '@/entities/admin/types'
import { Badge, Button, Card, EmptyState, Input } from '@/shared/ui'

export function SettingsPanels({ scenario }: { scenario?: string }) {
    const settingsQuery = useSystemSettingsQuery({ scenario })
    const settingPatchMutation = useSystemSettingPatchMutation({ scenario })
    const [drafts, setDrafts] = useState<Record<string, string>>({})
    const groupedSettings = useMemo(
        () =>
            (settingsQuery.data ?? []).reduce<Partial<Record<SystemSetting['group'], SystemSetting[]>>>((groups, setting) => {
                const key = setting.group
                groups[key] = [...(groups[key] ?? []), setting]
                return groups
            }, {}),
        [settingsQuery.data],
    )

    useEffect(() => {
        if (!settingsQuery.data) {
            return
        }

        setDrafts(
            Object.fromEntries(
                settingsQuery.data.map((setting) => [
                    setting.key,
                    setting.isSensitive ? '' : setting.value,
                ]),
            ),
        )
    }, [settingsQuery.data])

    if (settingsQuery.isError) {
        return <Card className="text-sm text-error-700 dark:text-error-300">{settingsQuery.error.message}</Card>
    }

    const settings = settingsQuery.data ?? []

    if (!settingsQuery.isLoading && settings.length === 0) {
        return (
            <EmptyState
                icon={Settings2}
                title="No settings to display"
                description="This scenario returned no settings contracts."
            />
        )
    }

    const handleSave = async (setting: SystemSetting) => {
        const nextValue = drafts[setting.key] ?? ''

        if (!setting.isSensitive && nextValue === setting.value) {
            return
        }

        if (setting.isSensitive && nextValue.trim().length === 0) {
            return
        }

        try {
            const updatedSetting = await settingPatchMutation.mutateAsync({
                key: setting.key,
                payload: {
                    value: nextValue,
                },
            })

            toast.success(`Updated ${updatedSetting.label}`, {
                description: updatedSetting.isSensitive ? 'Sensitive value rotated without exposing the stored secret.' : updatedSetting.value,
            })
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Unable to update this setting.'
            toast.error('Setting update failed', { description: message })
        }
    }

    return (
        <div className="space-y-4">
            <Card className="space-y-2 border-brand-200 bg-brand-50 dark:border-brand-900 dark:bg-brand-950">
                <div className="text-sm font-semibold text-brand-800 dark:text-brand-200">Editable policy surface</div>
                <p className="text-sm text-brand-700 dark:text-brand-300">
                    These panels now persist through the `/api/admin/settings` contract. Sensitive settings stay masked in the UI while still allowing admins to rotate the underlying value.
                </p>
                <p className="text-sm text-brand-700 dark:text-brand-300">
                    Publication settings also expose the break-glass contract: operator-owned remediation actions remain primary, while admin override is reserved for audited support incidents.
                </p>
            </Card>

            <div className="grid gap-6 xl:grid-cols-2">
                {Object.entries(groupedSettings).map(([group, entries]) => (
                    <Card key={group} className="space-y-4">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <div className="text-base font-semibold text-gray-900 dark:text-white">{formatSettingGroup(group as SystemSetting['group'])}</div>
                                <div className="text-sm text-gray-500">Policy values consumed by the `/web` frontend and backend contracts.</div>
                            </div>
                            <Badge tone="brand">{entries?.length ?? 0} settings</Badge>
                        </div>

                        <div className="space-y-4">
                            {(entries ?? []).map((entry) => {
                                const draftValue = drafts[entry.key] ?? ''
                                const dirty = entry.isSensitive ? draftValue.trim().length > 0 : draftValue !== entry.value
                                const isSaving = settingPatchMutation.isPending && settingPatchMutation.variables?.key === entry.key

                                return (
                                    <div key={entry.key} className="rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950">
                                        <div className="flex flex-wrap items-start justify-between gap-3">
                                            <div className="space-y-1">
                                                <div className="text-sm font-semibold text-gray-900 dark:text-white">{entry.label}</div>
                                                <div className="text-xs text-gray-500">{entry.description}</div>
                                            </div>
                                            <div className="flex flex-wrap gap-2">
                                                <Badge tone={entry.isSensitive ? 'warning' : 'neutral'}>
                                                    {entry.isSensitive ? 'Sensitive' : 'Visible'}
                                                </Badge>
                                                <Badge tone="brand">{entry.source}</Badge>
                                            </div>
                                        </div>

                                        <div className="mt-4 rounded-xl border border-gray-200 bg-white p-3 text-sm text-gray-600 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-300">
                                            Current value: {maskSettingValue(entry)}
                                        </div>

                                        <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-end">
                                            <Input
                                                className="md:flex-1"
                                                label={entry.isSensitive ? 'Replacement value' : 'Updated value'}
                                                type={entry.isSensitive ? 'password' : 'text'}
                                                value={draftValue}
                                                placeholder={entry.isSensitive ? 'Rotate the managed secret reference' : 'Update the contract value'}
                                                onChange={(event) =>
                                                    setDrafts((current) => ({ ...current, [entry.key]: event.target.value }))
                                                }
                                            />
                                            <Button
                                                variant={dirty ? 'primary' : 'secondary'}
                                                isLoading={isSaving}
                                                disabled={!dirty}
                                                onClick={() => void handleSave(entry)}
                                            >
                                                Save
                                            </Button>
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    </Card>
                ))}
            </div>
        </div>
    )
}
