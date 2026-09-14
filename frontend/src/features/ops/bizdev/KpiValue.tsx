import { useEffect, useState } from 'react'

// 대시보드 지표 중 아직 자동 집계가 없는 값 — 눌러서 고친다.
// 근거 데이터(계약·회계)가 붙으면 이 컴포넌트를 계산값으로 갈아 끼운다.
export default function KpiValue({ value, unit, onSaved, format }: {
  value: number | null
  unit: string
  onSaved: (next: number | null) => Promise<void>
  format: (v: number) => string
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => { setDraft(value === null ? '' : String(value)) }, [value])

  const commit = async () => {
    const text = draft.trim().replace(/,/g, '')
    const next = text === '' ? null : Number(text)
    if (next !== null && !Number.isFinite(next)) { setEditing(false); return }
    if (next !== value) {
      setSaving(true)
      try { await onSaved(next) } finally { setSaving(false) }
    }
    setEditing(false)
  }

  if (editing) {
    return (
      <input className="inp bz-kpi-input" autoFocus value={draft} disabled={saving}
             inputMode="decimal" placeholder="숫자"
             onChange={e => setDraft(e.target.value)}
             onBlur={commit}
             onKeyDown={e => {
               if (e.key === 'Enter') void commit()
               if (e.key === 'Escape') { setDraft(value === null ? '' : String(value)); setEditing(false) }
             }} />
    )
  }

  return (
    <button className="bz-kpi-edit" title="눌러서 입력" onClick={() => setEditing(true)}>
      {value === null ? <span className="bz-muted">미입력</span> : format(value)}
      {value !== null && <span className="u">{unit}</span>}
    </button>
  )
}
