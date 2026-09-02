import { apiSend } from '../api'
import { CERTAINTY_META } from '../constants'
import { CertaintyCell, EditableText } from './editors'
import FactCell from './FactCell'
import { parseShareholders } from './ShareholderBlock'
import type { SiteFact } from '../types'

// 사업개요 항목 표.
//  editable=false → 보기 전용(기본 화면). editable=true → 편집 팝업 안.
// 열 너비를 % 로 고정해, 나란히 놓인 카드끼리 표가 어긋나 보이지 않게 한다.
export default function FactTable({ facts, editable, canEdit, onChanged, showNote }: {
  facts: SiteFact[]
  editable?: boolean
  canEdit: boolean
  onChanged: () => void
  showNote?: boolean      // 경제성처럼 근거·단서를 함께 적어야 하는 섹션
}) {
  const patch = async (fact: SiteFact, body: Partial<SiteFact>) => {
    await apiSend('PATCH', `/api/bizdev/facts/${fact.id}/`, body)
    onChanged()
  }

  return (
    <table className={`tbl bz-doc-tbl bz-fact-tbl${showNote ? ' with-note' : ''}`}>
      <thead>
        <tr>
          <th>구분</th>
          <th>내용</th>
          {showNote && <th>비고</th>}
          <th>확정도</th>
        </tr>
      </thead>
      <tbody>
        {facts.map(f => (
          <tr key={f.id} className={
            f.input_spec?.parent ? 'bz-fact-child'
              : facts.some(x => x.input_spec?.parent === f.key) ? 'bz-fact-parent' : ''
          }>
            <td className="bz-fact-label">{f.label}</td>
            <td>
              {editable
                ? <FactCell fact={f} canEdit={canEdit} onSave={v => patch(f, { value: v })} />
                : <FactValue fact={f} />}
            </td>
            {showNote && (
              <td>
                {editable
                  ? <EditableText value={f.note} placeholder="—" disabled={!canEdit}
                                  onSave={v => patch(f, { note: v })} />
                  : (f.note || <span className="bz-muted">—</span>)}
              </td>
            )}
            <td>
              {editable
                ? <CertaintyCell value={f.certainty} disabled={!canEdit}
                                 onSave={v => patch(f, { certainty: v as SiteFact['certainty'] })} />
                : <CertaintyBadge value={f.certainty} />}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function CertaintyBadge({ value }: { value: SiteFact['certainty'] }) {
  const m = CERTAINTY_META[value] || CERTAINTY_META.unconfirmed
  return (
    <span className="bz-chip" style={{
      background: `color-mix(in srgb, ${m.color} 12%, transparent)`, color: m.color,
    }}>{m.label}</span>
  )
}

// 보기 전용 표시 — 입력 종류에 맞게 읽기 좋은 형태로 그린다.
function FactValue({ fact }: { fact: SiteFact }) {
  const spec = fact.input_spec || { input: 'text' }
  const value = (fact.value || '').trim()
  if (!value) return <span className="bz-muted">미정</span>

  // 사업 개요의 지분구조는 SPC 값을 비추는 읽기 전용이다
  if (spec.input === 'derived' && spec.display === 'shareholders') {
    return (
      <span>
        {parseShareholders(value).map(r => (
          <span key={r.name} className="bz-line">{r.name}{r.pct ? ` · ${r.pct}%` : ''}</span>
        ))}
      </span>
    )
  }

  switch (spec.input) {
    case 'aliases':
      return (
        <span className="bz-chips">
          {value.split('\n').filter(Boolean).map(a => (
            <span key={a} className="bz-chip bz-chip-alias">{a}</span>
          ))}
        </span>
      )
    case 'shareholders':
      return (
        <span>
          {value.split('\n').filter(Boolean).map(line => {
            const [name, pct] = line.split('|').map(s => s.trim())
            return <span key={line} className="bz-line">{name}{pct ? ` · ${pct}%` : ''}</span>
          })}
        </span>
      )
    case 'grid_distance': {
      const [km, ...rest] = value.split('·').map(s => s.trim())
      return <span>{[km ? `${km}km` : '', ...rest].filter(Boolean).join(' · ')}</span>
    }
    case 'substation':
      return <span>{value.endsWith('변전소') ? value : `${value}변전소`}</span>
    case 'number':
      return <span>{value}{spec.unit ? ` ${spec.unit}` : ''}</span>
    default:
      return (
        <span>
          {value.split('\n').map((line, i) => <span key={i} className="bz-line">{line}</span>)}
        </span>
      )
  }
}
