import { apiSend } from '../api'
import { CertaintyCell, EditableText } from './editors'
import type { SiteFact } from '../types'

// 사업개요 항목 표 — "구분 | 내용 | 확정도".
// 근거·비고 열은 화면에서 뺐다(값은 DB 에 남아 있어 md 내보내기에 쓸 수 있다).
// 항목 추가·삭제는 없다(정의는 서버 FACT_DEFS 가 소유). 값만 채운다.
export default function FactSection({ title, facts, canEdit, onChanged, compact, bare }: {
  title: string
  facts: SiteFact[]
  canEdit: boolean
  onChanged: () => void
  compact?: boolean   // 반폭 배치용 — 구분 열을 좁힌다
  bare?: boolean      // 카드 껍데기 없이 표만(다른 카드 안에 넣을 때)
}) {
  const patch = async (fact: SiteFact, body: Partial<SiteFact>) => {
    await apiSend('PATCH', `/api/bizdev/facts/${fact.id}/`, body)
    onChanged()
  }

  const unconfirmed = facts.filter(f => f.certainty === 'unconfirmed').length

  // 반폭 배치용 — 구분 열을 좁힌 것 외에는 full 과 같다.
  const compactTable = (
    <table className="tbl bz-doc-tbl" style={{ marginTop: 10 }}>
      <thead>
        <tr>
          <th style={{ width: 116 }}>구분</th>
          <th>내용</th>
          <th style={{ width: 84 }}>확정도</th>
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
          </tr>
        ))}
      </tbody>
    </table>
  )

  if (bare) return compactTable

  const fullTable = (
    <table className="tbl bz-doc-tbl" style={{ marginTop: 10 }}>
        <thead>
          <tr>
            <th style={{ width: 150 }}>구분</th>
            <th>내용</th>
            <th style={{ width: 90 }}>확정도</th>
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
            </tr>
          ))}
        </tbody>
    </table>
  )

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
      {compact ? compactTable : fullTable}
    </div>
  )
}
