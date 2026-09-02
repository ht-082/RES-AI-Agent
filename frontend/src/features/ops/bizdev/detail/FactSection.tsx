import { useState } from 'react'
import { Pencil } from 'lucide-react'
import FactTable from './FactTable'
import SectionModal from './SectionModal'
import ShareholderBlock from './ShareholderBlock'
import FactCell from './FactCell'
import { apiSend } from '../api'
import type { SiteFact } from '../types'

// 사업개요 항목 섹션 — 화면에서는 보기 전용이고, [편집] 버튼으로 팝업에서 고친다.
// 항목 추가·삭제는 없다(정의는 서버 FACT_DEFS 가 소유). 값과 확정도만 채운다.
export default function FactSection({ title, facts, canEdit, onChanged }: {
  title: string
  facts: SiteFact[]
  canEdit: boolean
  onChanged: () => void
}) {
  const [editing, setEditing] = useState(false)
  const unconfirmed = facts.filter(f => f.certainty === 'unconfirmed').length
  // 지분구조는 표 칸에 넣기엔 좁아 카드 폭 전체를 쓰는 별도 블록으로 뺀다
  const shareRows = facts.filter(f => f.input_spec?.input === 'shareholders')
  const tableRows = facts.filter(f => f.input_spec?.input !== 'shareholders')

  const saveShare = async (fact: SiteFact, value: string) => {
    await apiSend('PATCH', `/api/bizdev/facts/${fact.id}/`, { value })
    onChanged()
  }

  return (
    <div className="card block">
      <div className="bz-sec-head">
        <h3>{title}</h3>
        <div className="bz-sec-actions">
          {unconfirmed > 0 && (
            <span className="bz-chip" style={{ background: 'var(--amber-soft)', color: 'var(--amber)' }}>
              미확정 {unconfirmed}
            </span>
          )}
          {canEdit && (
            <button className="btn-ghost bz-edit-btn" onClick={() => setEditing(true)}>
              <Pencil size={13} /> 편집
            </button>
          )}
        </div>
      </div>

      <FactTable facts={tableRows} canEdit={canEdit} onChanged={onChanged} />
      {shareRows.map(f => (
        <ShareholderBlock key={f.id} fact={f}
                          targetName={facts.find(x => x.key === 'corp_name')?.value} />
      ))}

      {editing && (
        <SectionModal title={title} onClose={() => { setEditing(false); onChanged() }}>
          <FactTable facts={tableRows} editable canEdit={canEdit} onChanged={onChanged} />
          {shareRows.map(f => (
            <div key={f.id} style={{ marginTop: 14 }}>
              <div className="bz-block-title">{f.label}</div>
              <FactCell fact={f} canEdit={canEdit} onSave={v => saveShare(f, v)} />
            </div>
          ))}
        </SectionModal>
      )}
    </div>
  )
}
