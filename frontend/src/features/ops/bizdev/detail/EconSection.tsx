import { useState } from 'react'
import FactTable from './FactTable'
import SectionHead, { lastEdited } from './SectionHead'
import SectionModal from './SectionModal'
import Lines from './Lines'
import type { SiteFact } from '../types'

// 값이 있는 것만 숫자로. 빈 값·'미정'은 0 이 아니라 없음으로 다룬다.
function num(fact?: SiteFact): number | null {
  if (!fact) return null
  const v = parseFloat((fact.value || '').replace(/[^0-9.\-]/g, ''))
  return Number.isFinite(v) ? v : null
}
const fmt = (v: number) =>
  (Math.abs(v) >= 100 ? Math.round(v) : Math.round(v * 100) / 100).toLocaleString()
const pct = (part: number, whole: number) =>
  whole ? `${(part / whole * 100).toFixed(1)}%` : ''

const MUTED = <span className="bz-muted">미정</span>

// 사업비 — 금융모델 [총투자비] 표와 같은 구성. 합계 두 줄은 서버가 더해 둔다.
const COST_ROWS: Array<[string, string, boolean]> = [
  ['조사설계비', 'survey_design', false],
  ['토지비 (공사중)', 'land_cost', false],
  ['공사비', 'epc_cost', false],
  ['기타비용', 'other_cost', false],
  ['금융비용', 'finance_cost', false],
  ['총사업비', 'total_capex', true],
  ['Overfunding', 'overfunding', false],
  ['DSRA', 'dsra', false],
  ['총투자비', 'total_investment', true],
]
const PROFIT_ROWS: Array<[string, string]> = [
  ['연간 매출', 'annual_revenue'],
  ['영업이익', 'operating_profit'],
  ['당기순이익', 'net_profit'],
]
const IRR_ROWS: Array<[string, string]> = [
  ['E.IRR', 'e_irr'], ['P.IRR 세전', 'p_irr_pretax'], ['P.IRR 세후', 'p_irr_aftertax'],
]

// 경제성 및 총사업비 — 수익률을 맨 위에 크게, 그 아래 가정사항·사업비·손익을 표로.
// 편집은 다른 섹션과 같이 팝업 안 표에서 한다.
export default function EconSection({ title, facts, capacityMw, canEdit, onChanged, id }: {
  title: string
  facts: SiteFact[]
  capacityMw?: number
  canEdit: boolean
  onChanged: () => void
  id?: string
}) {
  const [editing, setEditing] = useState(false)
  const by = (key: string) => facts.find(f => f.key === key)
  const txt = (key: string) => (by(key)?.value || '').trim()
  const note = (key: string) => (by(key)?.note || '').trim()

  // ── 가정사항 — 공사기간·운영종료일·차입금 비율은 여기서 계산한다 ──
  const months = (from: string, to: string) => {
    if (!from || !to) return null
    const a = new Date(from), b = new Date(to)
    if (isNaN(a.getTime()) || isNaN(b.getTime())) return null
    return Math.max(0, Math.round((b.getTime() - a.getTime()) / 2_629_800_000))
  }
  const addYears = (from: string, years: number | null) => {
    if (!from || years === null) return ''
    const d = new Date(from)
    if (isNaN(d.getTime())) return ''
    d.setFullYear(d.getFullYear() + Math.trunc(years))
    return d.toISOString().slice(0, 10)
  }

  const cStart = txt('constr_start'), cEnd = txt('constr_end')
  const cMonths = months(cStart, cEnd)
  const opsYears = num(by('ops_years'))
  const opsEnd = addYears(cEnd, opsYears)
  const equity = num(by('equity_ratio'))
  const genHours = num(by('gen_hours'))
  const priceType = txt('price_type')

  // 단가는 체계에 따라 항목 수가 다르다. 행을 늘리면 PPA 와 SMP+REC 의
  // 표 높이가 달라지므로 한 줄로 합치고, 그 칸에 두 줄 자리를 미리 비워 둔다.
  const priceDetail =
    priceType === 'PPA'
      ? [txt('ppa_price') && `${txt('ppa_price')} 원/kWh`].filter(Boolean).join(' · ')
      : priceType === 'SMP + REC'
        ? [
            txt('smp_price') && `SMP ${txt('smp_price')} 원/kWh`,
            txt('rec_price') && `REC ${txt('rec_price')} 원/REC`,
            txt('rec_weight') && `가중치 ${txt('rec_weight')}`,
          ].filter(Boolean).join(' · ')
        : ''

  const assume: Array<[string, string]> = [
    ['공사기간', cStart && cEnd
      ? `${cStart} ~ ${cEnd}${cMonths !== null ? ` (${cMonths}개월)` : ''}` : ''],
    ['운영기간', opsYears === null ? ''
      : `${fmt(opsYears)}년${opsEnd ? ` (~${opsEnd})` : ''}`],
    ['자본금 : 차입금', equity === null ? '' : `${fmt(equity)} : ${fmt(100 - equity)}`],
    ['발전시간', genHours === null ? '' : `${fmt(genHours)} h`],
    ['가격 체계', priceType],
    ['단가', priceDetail],
  ]

  const capex = num(by('total_capex'))
  const revenue = num(by('annual_revenue'))
  const etc = by('etc')
  const esInvest = num(by('es_investment'))
  const empty = facts.every(f => !(f.value || '').trim())

  return (
    <div className="card block" id={id}>
      <SectionHead title={title} updatedAt={lastEdited(facts.map(f => f.updated_at))}
                   canEdit={canEdit} onEdit={() => setEditing(true)} />

      <div className="bz-scroll bz-scroll-pair">

      {/* 수익률 — 이 박스에서 가장 먼저 보아야 할 값 */}
      <div className="bz-irr-row">
        {IRR_ROWS.map(([label, key]) => {
          const v = num(by(key))
          return (
            <div key={key} className="bz-irr">
              <span className="bz-irr-label">{label}</span>
              <span className="bz-irr-val">
                {v === null ? <span className="bz-muted">미정</span> : fmt(v)}
                {v !== null && <span className="bz-irr-unit">%</span>}
              </span>
            </div>
          )
        })}
      </div>

      {empty && <p className="note">입력된 값이 없습니다.</p>}

      <div className="bz-econ-block-title">가정사항</div>
      <table className="tbl bz-doc-tbl bz-econ-tbl">
        <tbody>
          {assume.map(([label, value]) => (
            <tr key={label}>
              <th scope="row">{label}</th>
              <td className={label === '단가' ? 'bz-price-cell' : undefined} title={value}>
                {label === '단가'
                  ? <span className="bz-price-box">{value || MUTED}</span>
                  : (value || MUTED)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="bz-econ-block-title">사업비</div>
      <table className="tbl bz-doc-tbl bz-cost-tbl">
        <thead>
          <tr>
            <th>구분</th>
            <th className="bz-num">MW당</th>
            <th className="bz-num">비율</th>
            <th className="bz-num">금액</th>
            <th>비고</th>
          </tr>
        </thead>
        <tbody>
          {COST_ROWS.map(([label, key, sum]) => {
            const v = num(by(key))
            return (
              <tr key={key} className={sum ? 'bz-cost-sum' : undefined}>
                <th scope="row">{label}</th>
                <td className="bz-num">
                  {v !== null && capacityMw ? fmt(v / capacityMw) : ''}
                </td>
                <td className="bz-num">
                  {v !== null && capex && key !== 'total_investment' ? pct(v, capex) : ''}
                </td>
                <td className="bz-num">{v === null ? MUTED : fmt(v)}</td>
                <td className="bz-note" title={note(key)}>{note(key)}</td>
              </tr>
            )
          })}
          {esInvest !== null && (
            <tr>
              <th scope="row">E&S 총 투자비</th>
              <td className="bz-num" />
              <td className="bz-num" />
              <td className="bz-num">{fmt(esInvest)}</td>
              <td className="bz-note" title={note('es_investment')}>{note('es_investment')}</td>
            </tr>
          )}
        </tbody>
      </table>
      <p className="bz-econ-unit">단위: 억원{capacityMw ? ` · 설비용량 ${capacityMw}MW 기준` : ''}</p>

      <div className="bz-econ-block-title">손익</div>
      <table className="tbl bz-doc-tbl bz-profit-tbl">
        <thead>
          <tr>
            <th>구분</th>
            <th className="bz-num">금액</th>
            <th className="bz-num">매출 대비</th>
            <th>비고</th>
          </tr>
        </thead>
        <tbody>
          {PROFIT_ROWS.map(([label, key]) => {
            const v = num(by(key))
            return (
              <tr key={key}>
                <th scope="row">{label}</th>
                <td className="bz-num">{v === null ? MUTED : fmt(v)}</td>
                <td className="bz-num">
                  {v !== null && revenue && key !== 'annual_revenue' ? pct(v, revenue) : ''}
                </td>
                <td className="bz-note" title={note(key)}>{note(key)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {etc?.value && <div className="bz-econ-meta"><Lines text={etc.value} /></div>}
      </div>

      {editing && (
        <SectionModal title={title}
                      hint="총사업비·총투자비는 구성 항목에서 자동으로 더해집니다"
                      onClose={() => { setEditing(false); onChanged() }}>
          <FactTable facts={facts} editable canEdit={canEdit} onChanged={onChanged} showNote />
        </SectionModal>
      )}
    </div>
  )
}
