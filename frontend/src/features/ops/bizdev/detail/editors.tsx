import { useCallback, useEffect, useRef, useState } from 'react'

// 표 안에서 바로 고치는 입력들.
// 저장 시점: ① 입력이 멎고 0.8초 뒤 자동 저장 ② 포커스를 벗어날 때 ③ Enter(한 줄 입력).
// blur 하나에만 의존하면 탭을 옮기거나 창을 닫을 때 편집이 조용히 사라진다.
const AUTOSAVE_MS = 800

export function EditableText({ value, onSave, multiline, placeholder, disabled }: {
  value: string
  onSave: (next: string) => Promise<void> | void
  multiline?: boolean
  placeholder?: string
  disabled?: boolean
}) {
  const [draft, setDraft] = useState(value)
  const [saving, setSaving] = useState(false)
  const ref = useRef<HTMLTextAreaElement & HTMLInputElement>(null)
  const committed = useRef(value)
  const draftRef = useRef(value)          // 최신 입력값(콜백이 낡은 값을 붙잡지 않도록)
  const timer = useRef<number | undefined>(undefined)

  // 서버 값이 새로 내려오면(재조회 등) 따라간다.
  // 단 아직 저장되지 않은 편집이 남아 있으면 건드리지 않는다 — 옆 칸을 저장해
  // 목록이 갱신될 때 이 칸의 입력이 조용히 사라지는 것을 막는다.
  useEffect(() => {
    const dirty = draftRef.current !== committed.current
    if (dirty || document.activeElement === ref.current) return
    setDraft(value)
    draftRef.current = value
    committed.current = value
  }, [value])

  const commit = useCallback(async () => {
    window.clearTimeout(timer.current)
    const next = draftRef.current
    if (next === committed.current) return
    setSaving(true)
    try {
      await onSave(next)
      committed.current = next
    } catch {
      setDraft(committed.current)         // 실패하면 이전 값으로 되돌린다
      draftRef.current = committed.current
    } finally {
      setSaving(false)
    }
  }, [onSave])

  // 언마운트(탭 이동·화면 전환) 직전에 남은 편집을 흘려보내지 않는다
  useEffect(() => () => { void commit() }, [commit])

  const change = (next: string) => {
    setDraft(next)
    draftRef.current = next
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => { void commit() }, AUTOSAVE_MS)
  }

  const cancel = () => {
    window.clearTimeout(timer.current)
    setDraft(committed.current)
    draftRef.current = committed.current
  }

  const common = {
    ref,
    value: draft,
    placeholder: placeholder || '미정',
    disabled,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      change(e.target.value),
    onBlur: () => { void commit() },
    className: `bz-cell-input${saving ? ' saving' : ''}`,
  }

  if (multiline) {
    return (
      <textarea {...common}
                rows={Math.min(6, Math.max(1, draft.split('\n').length))}
                onKeyDown={e => { if (e.key === 'Escape') { cancel(); e.currentTarget.blur() } }} />
    )
  }
  return (
    <input {...common}
           onKeyDown={e => {
             if (e.key === 'Enter') { void commit(); e.currentTarget.blur() }
             if (e.key === 'Escape') { cancel(); e.currentTarget.blur() }
           }} />
  )
}

export function EditableSelect({ value, options, onSave, disabled, style }: {
  value: string
  options: Array<[string, string]>
  onSave: (next: string) => Promise<void> | void
  disabled?: boolean
  style?: React.CSSProperties
}) {
  const [saving, setSaving] = useState(false)
  return (
    <select className={`bz-cell-input${saving ? ' saving' : ''}`} value={value}
            disabled={disabled || saving} style={style}
            onChange={async e => {
              setSaving(true)
              try { await onSave(e.target.value) } finally { setSaving(false) }
            }}>
      {options.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
    </select>
  )
}

/** 확정/미확정 배지 겸 선택기 */
export function CertaintyCell({ value, onSave, disabled }: {
  value: string
  onSave: (next: string) => Promise<void> | void
  disabled?: boolean
}) {
  const meta: Record<string, { label: string; color: string }> = {
    confirmed: { label: '확정', color: 'var(--green-accent)' },
    unconfirmed: { label: '미확정', color: 'var(--amber)' },
    na: { label: '해당없음', color: '#b8c4bd' },
  }
  const m = meta[value] || meta.unconfirmed
  return (
    <EditableSelect
      value={value} disabled={disabled} onSave={onSave}
      options={[['confirmed', '확정'], ['unconfirmed', '미확정'], ['na', '해당없음']]}
      style={{
        color: m.color, fontWeight: 700, fontSize: 11,
        background: `color-mix(in srgb, ${m.color} 12%, transparent)`,
        borderRadius: 6, textAlign: 'center', width: 78,
      }}
    />
  )
}
