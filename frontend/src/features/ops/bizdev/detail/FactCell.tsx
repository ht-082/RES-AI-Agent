import { useEffect, useRef, useState } from 'react'
import { Search, X } from 'lucide-react'
import { apiGet } from '../api'
import { EditableSelect, EditableText } from './editors'
import type { SiteFact } from '../types'

// 항목 성격에 맞는 입력기. 저장 형식은 항상 텍스트라 md 내보내기에 영향이 없다.
//   select / number(단위) / date / address / substation / grid_distance /
//   aliases / shareholders / derived(읽기전용) / text
export default function FactCell({ fact, canEdit, onSave }: {
  fact: SiteFact
  canEdit: boolean
  onSave: (value: string) => Promise<void>
}) {
  const spec = fact.input_spec || { input: 'text' }

  switch (spec.input) {
    case 'computed':
      return (
        <div className="bz-derived">
          {fact.value || '—'}
          <span className="bz-derived-tag">구성 항목 합계</span>
        </div>
      )

    case 'derived':
      return (
        <div className="bz-derived">
          {fact.value || '—'}
          <span className="bz-derived-tag">경제성 항목에서 자동</span>
        </div>
      )

    case 'select':
      return (
        <EditableSelect value={fact.value} disabled={!canEdit} onSave={onSave}
                        options={[['', '미정'], ...(spec.options || []).map(o => [o, o] as [string, string])]} />
      )

    case 'number':
      return (
        <div className="bz-inline">
          <EditableText value={fact.value} placeholder="미정" disabled={!canEdit} onSave={onSave} />
          {spec.unit && <span className="bz-unit">{spec.unit}</span>}
        </div>
      )

    case 'date':
      return (
        <input className="bz-cell-input" type="date" value={fact.value || ''}
               disabled={!canEdit} onChange={e => void onSave(e.target.value)} />
      )

    case 'address':
      return <AddressCell fact={fact} canEdit={canEdit} onSave={onSave} />

    case 'substation':
      return <SubstationCell fact={fact} canEdit={canEdit} onSave={onSave} />

    case 'grid_distance':
      return <GridDistanceCell fact={fact} canEdit={canEdit} onSave={onSave} />

    case 'aliases':
      return <AliasCell fact={fact} canEdit={canEdit} onSave={onSave} />

    case 'shareholders':
      return <ShareholderCell fact={fact} canEdit={canEdit} onSave={onSave} />

    default:
      return (
        <EditableText value={fact.value} multiline disabled={!canEdit} onSave={onSave} />
      )
  }
}

// ── 위치: 대표 필지 주소 한 줄 ──────────────────────────────────────
function AddressCell({ fact, canEdit, onSave }: CellProps) {
  return (
    <div>
      <EditableText value={fact.value} placeholder="예: 충남 홍성군 갈산면 기산리 780"
                    disabled={!canEdit} onSave={onSave} />
      <div className="bz-hint">이 주소의 시·군이 계통·조례 조회 기준이 됩니다</div>
    </div>
  )
}

// ── 연계점: KEPCO 변전소 검색 ───────────────────────────────────────
interface Substation { name: string; region: string; available_mw: number }

function SubstationCell({ fact, canEdit, onSave }: CellProps) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [rows, setRows] = useState<Substation[]>([])
  const [info, setInfo] = useState<Substation | null>(null)
  const boxRef = useRef<HTMLDivElement>(null)

  // 선택된 변전소의 여유용량을 옆에 보여 준다
  useEffect(() => {
    let cancelled = false
    if (!fact.value) { setInfo(null); return }
    apiGet<Substation[]>(`/api/bizdev/grid/substations/?q=${encodeURIComponent(fact.value)}`)
      .then(d => { if (!cancelled) setInfo(d.find(s => s.name === fact.value) || null) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [fact.value])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    apiGet<Substation[]>(`/api/bizdev/grid/substations/?q=${encodeURIComponent(q)}`)
      .then(d => { if (!cancelled) setRows(d) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [open, q])

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  return (
    <div ref={boxRef} style={{ position: 'relative' }}>
      <button className="bz-cell-input bz-picker" disabled={!canEdit}
              onClick={() => setOpen(v => !v)}>
        <span>{fact.value ? (fact.value.endsWith('변전소') ? fact.value : `${fact.value}변전소`) : '변전소 선택'}</span>
        <Search size={12} />
      </button>
      {info && (
        <div className="bz-hint">{info.region} · 접속 여유 {info.available_mw.toLocaleString()}MW</div>
      )}
      {open && (
        <div className="bz-dropdown">
          <input className="bz-cell-input" autoFocus placeholder="변전소·지역 검색"
                 value={q} onChange={e => setQ(e.target.value)} />
          <div className="bz-dropdown-list">
            {rows.map(s => (
              <button key={s.name + s.region} className="bz-dropdown-item"
                      onClick={() => { void onSave(s.name); setOpen(false); setQ('') }}>
                <span>{s.name}<span className="bz-muted"> · {s.region}</span></span>
                <span className="bz-muted">{s.available_mw.toLocaleString()}MW</span>
              </button>
            ))}
            {rows.length === 0 && <div className="bz-hint" style={{ padding: 6 }}>검색 결과 없음</div>}
          </div>
        </div>
      )}
    </div>
  )
}

// ── 연계거리: 거리(km) · 방식 · 전압 ────────────────────────────────
const METHODS: Array<[string, string]> = [['', '방식'], ['지중', '지중'], ['가공', '가공']]
const VOLTAGES: Array<[string, string]> = [
  ['', '전압'], ['22.9kV', '22.9kV'], ['154kV', '154kV'], ['345kV', '345kV'],
]

function GridDistanceCell({ fact, canEdit, onSave }: CellProps) {
  const [km = '', method = '', voltage = ''] = (fact.value || '').split('·').map(x => x.trim())
  const compose = (k: string, m: string, v: string) =>
    [k, m, v].filter(Boolean).join(' · ')
  return (
    <div className="bz-inline">
      <EditableText value={km} placeholder="거리" disabled={!canEdit}
                    onSave={v => onSave(compose(v, method, voltage))} />
      <span className="bz-unit">km</span>
      <EditableSelect value={method} options={METHODS} disabled={!canEdit}
                      onSave={v => onSave(compose(km, v, voltage))} style={{ width: 68 }} />
      <EditableSelect value={voltage} options={VOLTAGES} disabled={!canEdit}
                      onSave={v => onSave(compose(km, method, v))} style={{ width: 82 }} />
    </div>
  )
}

// ── 별칭: 칩으로 추가·삭제 (한 줄에 하나로 저장) ────────────────────
function AliasCell({ fact, canEdit, onSave }: CellProps) {
  const [adding, setAdding] = useState('')
  const list = (fact.value || '').split('\n').map(x => x.trim()).filter(Boolean)

  const add = () => {
    const next = adding.trim()
    if (!next || list.includes(next)) { setAdding(''); return }
    void onSave([...list, next].join('\n'))
    setAdding('')
  }

  return (
    <div>
      <div className="bz-chips">
        {list.map(a => (
          <span key={a} className="bz-chip bz-chip-alias">
            {a}
            {canEdit && (
              <button onClick={() => void onSave(list.filter(x => x !== a).join('\n'))}
                      aria-label="별칭 삭제"><X size={10} /></button>
            )}
          </span>
        ))}
        {list.length === 0 && <span className="bz-muted" style={{ fontSize: 11 }}>없음</span>}
      </div>
      {canEdit && (
        <input className="bz-cell-input" placeholder="+ 별칭 추가 후 Enter" value={adding}
               onChange={e => setAdding(e.target.value)}
               onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
               onBlur={add} />
      )}
    </div>
  )
}

// ── 지분구조: 주주명 | 지분% 행 (합계 100% 검증) ────────────────────
// 빈 행은 저장하지 않으므로(저장 형식이 텍스트라 빈 줄이 쌓인다) 화면 상태로만
// 들고 있다가, 이름이나 지분을 채우는 순간 저장한다.
function ShareholderCell({ fact, canEdit, onSave }: CellProps) {
  const NL = String.fromCharCode(10)
  const parse = (v: string) => (v || '').split(NL).map(x => x.trim()).filter(Boolean)
    .map(line => {
      const [name, pct] = line.split('|').map(s => s.trim())
      return { name: name || '', pct: pct || '' }
    })

  const [rows, setRows] = useState(() => parse(fact.value))
  const saved = useRef(fact.value)

  // 서버 값이 바뀌면 따라간다(내가 저장해 돌아온 값이면 그대로)
  useEffect(() => {
    if (fact.value !== saved.current) {
      saved.current = fact.value
      setRows(parse(fact.value))
    }
  }, [fact.value])

  const total = rows.reduce((a, r) => a + (parseFloat(r.pct) || 0), 0)

  const commit = (next: Array<{ name: string; pct: string }>) => {
    setRows(next)
    const text = next.filter(r => r.name || r.pct)
      .map(r => `${r.name} | ${r.pct}`).join(NL)
    saved.current = text
    void onSave(text)
  }

  return (
    <div>
      {rows.map((r, i) => (
        <div key={i} className="bz-inline" style={{ marginBottom: 2 }}>
          <EditableText value={r.name} placeholder="주주명" disabled={!canEdit}
                        onSave={v => commit(rows.map((x, j) => j === i ? { ...x, name: v } : x))} />
          <div style={{ width: 58, flexShrink: 0 }}>
            <EditableText value={r.pct} placeholder="%" disabled={!canEdit}
                          onSave={v => commit(rows.map((x, j) => j === i ? { ...x, pct: v } : x))} />
          </div>
          <span className="bz-unit">%</span>
          {canEdit && (
            <button className="btn-ghost" style={{ padding: 2 }} aria-label="주주 삭제"
                    onClick={() => commit(rows.filter((_, j) => j !== i))}><X size={11} /></button>
          )}
        </div>
      ))}
      <div className="bz-inline" style={{ justifyContent: 'space-between' }}>
        {canEdit && (
          <button className="btn-ghost" style={{ fontSize: 11, padding: '2px 6px' }}
                  onClick={() => setRows([...rows, { name: '', pct: '' }])}>+ 주주 추가</button>
        )}
        {rows.length > 0 && (
          <span className="bz-hint" style={{ color: Math.abs(total - 100) < 0.01 ? 'var(--ink-faint)' : 'var(--amber)' }}>
            합계 {total}%{Math.abs(total - 100) < 0.01 ? '' : ' (100% 아님)'}
          </span>
        )}
      </div>
    </div>
  )
}

interface CellProps {
  fact: SiteFact
  canEdit: boolean
  onSave: (value: string) => Promise<void>
}
