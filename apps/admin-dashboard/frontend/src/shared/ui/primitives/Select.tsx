import {
    type ChangeEvent,
    type FocusEvent,
    type KeyboardEvent,
    type SelectHTMLAttributes,
    useEffect,
    useId,
    useMemo,
    useRef,
    useState,
} from 'react'
import { Check, ChevronDown } from 'lucide-react'
import { cn } from '@/shared/lib/cn'

export interface SelectOption {
    label: string
    value: string
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
    label?: string
    hint?: string
    error?: string
    placeholder?: string
    options: SelectOption[]
}

function normalizeValue(value: SelectProps['value'] | SelectProps['defaultValue']) {
    if (Array.isArray(value)) {
        return value[0] ?? ''
    }

    if (typeof value === 'number') {
        return String(value)
    }

    return value ?? ''
}

export function Select({
    className,
    label,
    hint,
    error,
    options,
    id,
    value,
    defaultValue,
    onChange,
    onBlur,
    name,
    disabled,
    required,
    placeholder,
    'aria-label': ariaLabel,
    'aria-describedby': ariaDescribedBy,
}: SelectProps) {
    const generatedId = useId()
    const fieldId = id ?? label?.toLowerCase().replace(/\s+/g, '-') ?? generatedId
    const helperId = `${fieldId}-helper`
    const initialValue = useMemo(() => {
        const controlledValue = normalizeValue(value)
        if (controlledValue.length > 0) {
            return controlledValue
        }

        const fallbackValue = normalizeValue(defaultValue)
        if (fallbackValue.length > 0) {
            return fallbackValue
        }

        return options[0]?.value ?? ''
    }, [defaultValue, options, value])
    const [selectedValue, setSelectedValue] = useState(initialValue)
    const [isOpen, setIsOpen] = useState(false)
    const wrapperRef = useRef<HTMLDivElement | null>(null)
    const listboxId = `${fieldId}-listbox`
    const selectedOption = options.find((option) => option.value === selectedValue) ?? options[0]
    const hasLabel = Boolean(label)

    useEffect(() => {
        const nextValue = normalizeValue(value)
        if (nextValue.length > 0) {
            setSelectedValue(nextValue)
            return
        }

        if (!value && options[0] && !options.some((option) => option.value === selectedValue)) {
            setSelectedValue(options[0].value)
        }
    }, [options, selectedValue, value])

    useEffect(() => {
        if (value !== undefined) {
            return
        }

        const fallbackValue = normalizeValue(defaultValue)
        if (fallbackValue.length > 0) {
            setSelectedValue(fallbackValue)
        }
    }, [defaultValue, value])

    useEffect(() => {
        if (!isOpen) {
            return
        }

        function handlePointerDown(event: MouseEvent) {
            if (!wrapperRef.current?.contains(event.target as Node)) {
                setIsOpen(false)
            }
        }

        function handleEscape(event: globalThis.KeyboardEvent) {
            if (event.key === 'Escape') {
                setIsOpen(false)
            }
        }

        window.addEventListener('mousedown', handlePointerDown)
        window.addEventListener('keydown', handleEscape)
        return () => {
            window.removeEventListener('mousedown', handlePointerDown)
            window.removeEventListener('keydown', handleEscape)
        }
    }, [isOpen])

    function emitChange(nextValue: string) {
        onChange?.({
            target: { value: nextValue, name },
            currentTarget: { value: nextValue, name },
        } as ChangeEvent<HTMLSelectElement>)
    }

    function handleSelect(nextValue: string) {
        if (disabled) {
            return
        }

        if (value === undefined) {
            setSelectedValue(nextValue)
        }

        emitChange(nextValue)
        setIsOpen(false)
    }

    function handleBlur(event: FocusEvent<HTMLButtonElement>) {
        const nextFocused = event.relatedTarget as Node | null
        if (wrapperRef.current?.contains(nextFocused)) {
            return
        }

        setIsOpen(false)
        onBlur?.(event as unknown as FocusEvent<HTMLSelectElement>)
    }

    function handleTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
        if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            setIsOpen(true)
        }
    }

    return (
        <div className={cn('relative flex w-full flex-col gap-1.5', isOpen && 'z-[90]')}>
            {label ? <span className="text-sm font-medium text-gray-700 dark:text-gray-200">{label}</span> : null}
            <div ref={wrapperRef} className={cn('relative', isOpen && 'z-[90]')}>
                <input disabled={disabled} name={name} required={required} type="hidden" value={selectedValue} />
                <button
                    aria-controls={listboxId}
                    aria-describedby={error || hint ? ariaDescribedBy ?? helperId : ariaDescribedBy}
                    aria-expanded={isOpen}
                    aria-haspopup="listbox"
                    aria-invalid={error ? 'true' : 'false'}
                    aria-label={ariaLabel ?? label}
                    className={cn(
                        'group flex w-full items-center justify-between gap-3 rounded-[26px] border border-brand-200/85 bg-white px-5 text-left text-slate-900 shadow-[0_16px_34px_-28px_rgba(37,99,235,0.45)] outline-none transition-all duration-200 hover:border-brand-300 hover:shadow-[0_20px_40px_-24px_rgba(37,99,235,0.32)] focus-visible:border-brand-400 focus-visible:ring-4 focus-visible:ring-brand-500/14 dark:border-brand-400/14 dark:bg-[linear-gradient(180deg,rgba(8,18,31,0.94),rgba(12,25,44,0.98))] dark:text-white dark:shadow-[0_28px_60px_-32px_rgba(6,27,63,0.85)] dark:hover:border-brand-300/40 dark:hover:bg-[linear-gradient(180deg,rgba(10,22,38,0.98),rgba(14,29,51,1))] dark:focus-visible:border-brand-300',
                        hasLabel ? 'py-4 text-base font-medium' : 'py-3.5 text-sm font-semibold',
                        isOpen &&
                            'border-brand-400 shadow-[0_22px_46px_-24px_rgba(37,99,235,0.35)] dark:border-brand-300/60 dark:bg-[linear-gradient(180deg,rgba(10,22,38,0.98),rgba(14,29,51,1))]',
                        disabled && 'cursor-not-allowed opacity-60',
                        error && 'border-error-500 focus-visible:border-error-500 focus-visible:ring-error-500/10 dark:border-error-500',
                        className,
                    )}
                    disabled={disabled}
                    id={fieldId}
                    onBlur={handleBlur}
                    onClick={() => setIsOpen((open) => !open)}
                    onKeyDown={handleTriggerKeyDown}
                    type="button"
                >
                    <span className="flex min-w-0 items-center gap-3">
                        <span className="h-3 w-3 rounded-full bg-gradient-to-br from-brand-500 to-brand-300 shadow-[0_0_0_6px_rgba(59,130,246,0.12)] dark:shadow-[0_0_0_6px_rgba(59,130,246,0.18)]" />
                        <span className="truncate">{selectedOption?.label ?? placeholder ?? 'Chọn một tùy chọn'}</span>
                    </span>
                    <ChevronDown
                        size={18}
                        className={cn(
                            'shrink-0 text-slate-400 transition-transform duration-200 group-hover:text-brand-500 dark:text-slate-300',
                            isOpen && 'rotate-180 text-brand-500',
                        )}
                    />
                </button>

                <div
                    className={cn(
                        'pointer-events-none absolute left-0 right-0 top-[calc(100%+0.7rem)] z-[95] origin-top rounded-[24px] border border-brand-100 bg-white/98 p-2 opacity-0 shadow-[0_28px_70px_-34px_rgba(15,23,42,0.3)] backdrop-blur-xl transition-all duration-200 dark:border-brand-400/16 dark:bg-[linear-gradient(180deg,rgba(7,15,28,0.98),rgba(10,21,39,0.98))] dark:shadow-[0_34px_82px_-30px_rgba(2,8,23,0.82)]',
                        isOpen && 'pointer-events-auto translate-y-0 scale-100 opacity-100',
                        !isOpen && '-translate-y-2 scale-[0.98]',
                    )}
                    id={listboxId}
                    role="listbox"
                >
                    <div className="space-y-1.5">
                        {options.map((option) => {
                            const isSelected = option.value === selectedValue

                            return (
                                <button
                                    aria-selected={isSelected}
                                    className={cn(
                                        'flex w-full items-center justify-between gap-3 rounded-[18px] px-4 py-3 text-left text-[15px] font-medium text-slate-700 transition-colors duration-150 hover:bg-brand-50 hover:text-brand-700 focus-visible:bg-brand-50 focus-visible:text-brand-700 focus-visible:outline-none dark:text-slate-200 dark:hover:bg-brand-400/12 dark:hover:text-brand-50 dark:focus-visible:bg-brand-400/12',
                                        isSelected &&
                                            'bg-brand-50 text-brand-700 shadow-[inset_0_0_0_1px_rgba(59,130,246,0.14)] dark:bg-[linear-gradient(180deg,rgba(32,67,129,0.32),rgba(18,42,82,0.34))] dark:text-brand-50 dark:shadow-[inset_0_0_0_1px_rgba(96,165,250,0.22)]',
                                    )}
                                    key={option.value}
                                    onClick={() => handleSelect(option.value)}
                                    role="option"
                                    type="button"
                                >
                                    <span className="flex items-center gap-3">
                                        <span
                                            className={cn(
                                                'h-2.5 w-2.5 rounded-full bg-slate-200 transition-colors dark:bg-slate-600',
                                                isSelected && 'bg-brand-500 dark:bg-brand-300',
                                            )}
                                        />
                                        <span>{option.label}</span>
                                    </span>
                                    {isSelected ? <Check size={16} className="text-brand-500 dark:text-brand-300" /> : null}
                                </button>
                            )
                        })}
                    </div>
                </div>
            </div>
            {error ? (
                <span className="text-xs font-medium text-error-600" id={helperId}>
                    {error}
                </span>
            ) : null}
            {!error && hint ? (
                <span className="text-xs text-gray-500" id={helperId}>
                    {hint}
                </span>
            ) : null}
        </div>
    )
}
