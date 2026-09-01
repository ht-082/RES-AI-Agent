import { apiSend } from '../api'
import { CertaintyCell, EditableText } from './editors'
import type { SiteFact } from '../types'

// 사업개요 항목 표 — 양식의 "구분 | 내용 | 확정도 | 근거·비고" 그대로.
// 항목 추가·삭제는 없다(정의는 서버 FACT_DEFS 가 소유). 값만 채운다.
export default function FactSection({ title, facts, canEdit, onChanged }: {
  title: string
  facts: SiteFact[]
  canEdit: boolean
  onChanged: () => void
}) {
  const patch = async (fact: SiteFact, body: Partial<SiteFact>) => {
    await apiSend('PATCH', `/api/bizdev/facts/${fact.id}/`, body)
    onChanged()
  }

  const unconfirmed = facts.filter(f => f.certainty === 'unconfirmed').length

  return (
    <div className="card block">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h3>{title}</h3>
        {unconfirmed > 0 && (
          <span className="bz-chip" style={{ background: 'var(--amber-soft)', color: 'var(--amber)' }}>
            미확정 {unconfirmed}
          </span>
        )}
      </div>
      <table className="tbl bz-doc-tbl" style={{ marginTop: 10 }}>
        <thead>
          <tr>
            <th style={{ width: 150 }}>구분</th>
            <th>내용</th>
            <th style={{ width: 90 }}>확정도</th>
            <th style={{ width: 150 }}>근거</th>
            <th style={{ width: 130 }}>비고</th>
          </tr>
        </thead>
        <tbody>
          {facts.map(f => (
            <tr key={f.id}>
              <td style={{ fontWeight: 600, color: 'var(--ink-soft)' }}>{f.label}</td>
              <td>
                <EditableText value={f.value} multiline disabled={!canEdit}
                              onSave={v => patch(f, { value: v })} />
              </td>
              <td>
                <CertaintyCell value={f.certainty} disabled={!canEdit}
                               onSave={v => patch(f, { certainty: v as SiteFact['certainty'] })} />
              </td>
              <td>
                <EditableText value={f.source} placeholder="—" disabled={!canEdit}
                              onSave={v => patch(f, { source: v })} />
              </td>
              <td>
                <EditableText value={f.note} placeholder="—" disabled={!canEdit}
                              onSave={v => patch(f, { note: v })} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
