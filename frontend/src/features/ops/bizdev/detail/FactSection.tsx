import { useState } from 'react'
import FactTable from './FactTable'
import SectionHead, { lastEdited } from './SectionHead'
import SectionModal from './SectionModal'
import ShareholderBlock from './ShareholderBlock'
import FactCell from './FactCell'
import { apiSend } from '../api'
import type { SiteFact } from '../types'

// 사업개요 항목 섹션 — 화면에서는 보기 전용이고, [편집] 버튼으로 팝업에서 고친다.
// 항목 추가·삭제는 없다(정의는 서버 FACT_DEFS 가 소유). 값과 확정도만 채운다.
export default function FactSection({ title, facts, canEdit, onChanged, extra, modalExtra, showNote }: {
  title: string
  facts: SiteFact[]
  canEdit: boolean
  onChanged: () => void
  extra?: React.ReactNode        // 머리에 덧붙일 요소
  modalExtra?: React.ReactNode   // 편집 팝업 맨 위에 덧붙일 요소(등기부 업로드 등)
  showNote?: boolean             // 비고 열을 함께 보여 줄지
}) {
  const [editing, setEditing] = useState(false)
  const updatedAt = lastEdited(facts.map(f => f.updated_at))
  // 지분구조는 표 칸에 넣기엔 좁아 카드 폭 전체를 쓰는 별도 블록으로 뺀다
  const shareRows = facts.filter(f => f.input_spec?.input === 'shareholders')
  const tableRows = facts.filter(f => f.input_spec?.input !== 'shareholders')

  const saveShare = async (fact: SiteFact, value: string) => {
    await apiSend('PATCH', `/api/bizdev/facts/${fact.id}/`, { value })
    onChanged()
  }

  return (
    <div className="card block">
      <SectionHead title={title} updatedAt={updatedAt} canEdit={canEdit}
                   onEdit={() => setEditing(true)} extra={extra} />

      <FactTable facts={tableRows} canEdit={canEdit} onChanged={onChanged} showNote={showNote} />
      {shareRows.map(f => (
        <ShareholderBlock key={f.id} fact={f}
                          targetName={facts.find(x => x.key === 'corp_name')?.value} />
      ))}

      {editing && (
        <SectionModal title={title} onClose={() => { setEditing(false); onChanged() }}>
          {modalExtra}
          <FactTable facts={tableRows} editable canEdit={canEdit} onChanged={onChanged}
                     showNote={showNote} />
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
