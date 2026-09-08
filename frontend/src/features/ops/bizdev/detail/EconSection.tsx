import { useState } from 'react'
import FactTable from './FactTable'
import SectionHead, { lastEdited } from './SectionHead'
import SectionModal from './SectionModal'
import Lines from './Lines'
import type { SiteFact } from '../types'

// 값이 있는 것만 숫자로. 빈 값·미정은 0 이 아니라 '없음'으로 다룬다.
function num(fact?: SiteFact): number | null {
  if (!fact) return null
  const v = parseFloat((fact.value || '').replace(/[^0-9.\-]/g, ''))
  return Number.isFinite(v) ? v : null
}
const fmt = (v: number) =>
  (Math.abs(v) >= 100 ? Math.round(v) : Math.round(v * 10) / 10).toLocaleString()

// 경제성 및 총사업비 — 보기 화면은 표 대신 숫자 타일과 비교 막대.
// 성격이 셋으로 갈린다: 금액(타일) / 손익 흐름(막대) / 수익률(비교 막대).
// 편집은 다른 섹션과 같이 팝업 안 표에서 한다.
export default function EconSection({ title, facts, canEdit, onChanged }: {
  title: string
  facts: SiteFact[]
  canEdit: boolean
  onChanged: () => void
}) {
  const [editing, setEditing] = useState(false)
  const by = (key: string) => facts.find(f => f.key === key)

  const money: Array<[string, string]> = [
    ['총사업비', 'total_capex'], ['EPC 공사비', 'epc_cost'], ['E&S 투자비', 'es_investment'],
  ]
  const profit: Array<[string, string]> = [
    ['연간 매출', 'annual_revenue'], ['영업이익', 'operating_profit'], ['당기순이익', 'net_profit'],
  ]
  const irr: Array<[string, string]> = [
    ['E.IRR', 'e_irr'], ['P.IRR 세전', 'p_irr_pretax'], ['P.IRR 세후', 'p_irr_aftertax'],
  ]
  // 막대 길이 기준 — 가장 큰 값에 맞춘다(값이 없으면 막대를 그리지 않는다)
  const profitMax = Math.max(0, ...profit.map(([, k]) => num(by(k)) ?? 0))
  const irrMax = Math.max(0, ...irr.map(([, k]) => num(by(k)) ?? 0))

  const etc = by('etc')
  const extras = [by('equity_debt'), by('gen_hours')].filter(Boolean) as SiteFact[]
  const empty = [...money, ...profit, ...irr].every(([, k]) => num(by(k)) === null)

  const bars = (rows: Array<[string, string]>, max: number, unit: string, color: string) => (
    <div className="bz-econ-bars">
      {rows.map(([label, key]) => {
        const v = num(by(key))
        return (
          <div key={key} className="bz-econ-bar-row">
            <span className="bz-econ-bar-label">{label}</span>
            <div className="bz-bar bz-econ-bar">
              {v !== null && max > 0 && (
                <div className="bz-bar-fill"
                     style={{ width: `${Math.max(2, (Math.max(v, 0) / max) * 100)}%`, background: color }} />
              )}
            </div>
            <span className="bz-econ-bar-val">
              {v === null ? <span className="bz-muted">미정</span> : `${fmt(v)}${unit}`}
            </span>
          </div>
        )
      })}
    </div>
  )

  return (
    <div className="card block">
      <SectionHead title={title} updatedAt={lastEdited(facts.map(f => f.updated_at))}
                   canEdit={canEdit} onEdit={() => setEditing(true)} />

      {empty && <p className="note" style={{ marginTop: 10 }}>입력된 값이 없습니다.</p>}

      <div className="bz-econ-tiles">
        {money.map(([label, key]) => {
          const v = num(by(key))
          return (
            <div key={key} className="bz-econ-tile">
              <span className="bz-econ-tile-label">{label}</span>
              <span className="bz-econ-tile-val">
                {v === null ? <span className="bz-muted">미정</span> : fmt(v)}
                {v !== null && <span className="bz-econ-tile-unit">억원</span>}
              </span>
            </div>
          )
        })}
      </div>

      <div className="bz-econ-block-title">손익</div>
      {bars(profit, profitMax, '억원', 'var(--brand)')}

      <div className="bz-econ-block-title">수익률</div>
      {bars(irr, irrMax, '%', 'var(--green-accent)')}

      {extras.length > 0 && (
        <div className="bz-econ-meta">
          {extras.map(f => (
            <span key={f.id}>
              <span className="bz-econ-meta-label">{f.label.replace(/\s*\(.*\)$/, '')}</span>
              {f.value || '미정'}
            </span>
          ))}
        </div>
      )}
      {etc?.value && (
        <div className="bz-econ-meta"><Lines text={etc.value} /></div>
      )}

      {editing && (
        <SectionModal title={title} onClose={() => { setEditing(false); onChanged() }}>
          <FactTable facts={facts} editable canEdit={canEdit} onChanged={onChanged} showNote />
        </SectionModal>
      )}
    </div>
  )
}
