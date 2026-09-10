import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { apiSend } from '../api'
import SectionHead, { lastEdited } from './SectionHead'
import SectionModal from './SectionModal'
import Lines from './Lines'
import { EditableSelect, EditableText } from './editors'
import { shortDate } from '../constants'
import type { DefectItem } from '../types'

const STATUS: Array<[string, string]> = [
  ['open', '접수'], ['doing', '조치중'], ['done', '완료'], ['hold', '보류'],
]
const COLOR: Record<string, string> = {
  open: 'var(--amber)', doing: 'var(--brand)',
  done: 'var(--green-accent)', hold: '#b8c4bd',
}

// 하자 보수 현황 — 양식 §1-4
export default function DefectCard({ siteId, defects, canEdit, onChanged, onError, id }: {
  siteId: string
  defects: DefectItem[]
  canEdit: boolean
  onChanged: () => void
  onError: (msg: string) => void
  id?: string
}) {
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)

  const patch = async (row: DefectItem, body: Record<string, unknown>) => {
    await apiSend('PATCH', `/api/bizdev/defects/${row.id}/`, body)
    onChanged()
  }
  const add = async () => {
    setBusy(true)
    try {
      await apiSend('POST', '/api/bizdev/defects/', {
        site: siteId, found_date: new Date().toISOString().slice(0, 10), status: 'open',
      })
      onChanged()
    } catch (e) { onError(e instanceof Error ? e.message : '추가 실패') } finally { setBusy(false) }
  }
  const remove = async (row: DefectItem) => {
    if (!confirm('이 하자 건을 삭제할까요?')) return
    try {
      await apiSend('DELETE', `/api/bizdev/defects/${row.id}/`)
      onChanged()
    } catch (e) { onError(e instanceof Error ? e.message : '삭제 실패') }
  }

  const open = defects.filter(d => d.status !== 'done').length

  const table = (editable: boolean) => (
    <table className="tbl bz-doc-tbl bz-defect-tbl">
      <thead>
        <tr>
          <th>발생일</th>
          <th>설비 · 부위</th>
          <th>내용</th>
          <th>상태</th>
          <th>조치일</th>
          <th>조치 주체</th>
          {canEdit && editable && <th className="bz-col-act" />}
        </tr>
      </thead>
      <tbody>
        {defects.length === 0 && (
          <tr><td colSpan={canEdit && editable ? 7 : 6}
                  style={{ textAlign: 'center', color: 'var(--ink-faint)', fontSize: 12 }}>
            등록된 하자가 없습니다.
          </td></tr>
        )}
        {defects.map(row => (
          <tr key={row.id}>
            <td className="bz-nowrap">
              {editable
                ? <input className="bz-cell-input" type="date" value={row.found_date || ''}
                         disabled={!canEdit}
                         onChange={e => patch(row, { found_date: e.target.value || null })} />
                : (shortDate(row.found_date) || <span className="bz-muted">—</span>)}
            </td>
            <td title={row.part}>
              {editable
                ? <EditableText value={row.part} disabled={!canEdit} placeholder="모듈 · 인버터"
                                onSave={v => patch(row, { part: v })} />
                : row.part}
            </td>
            <td title={row.summary}>
              {editable
                ? <EditableText value={row.summary} multiline disabled={!canEdit} placeholder="내용"
                                onSave={v => patch(row, { summary: v })} />
                : <Lines text={row.summary} />}
            </td>
            <td>
              {editable ? (
                <EditableSelect value={row.status} options={STATUS} disabled={!canEdit}
                                onSave={v => patch(row, { status: v })}
                                style={{
                                  color: COLOR[row.status], fontWeight: 700, fontSize: 11,
                                  background: `color-mix(in srgb, ${COLOR[row.status]} 12%, transparent)`,
                                  borderRadius: 6, textAlign: 'center',
                                }} />
              ) : (
                <span className="bz-chip" style={{
                  background: `color-mix(in srgb, ${COLOR[row.status]} 12%, transparent)`,
                  color: COLOR[row.status],
                }}>{row.status_label}</span>
              )}
            </td>
            <td className="bz-nowrap">
              {editable
                ? <input className="bz-cell-input" type="date" value={row.fixed_date || ''}
                         disabled={!canEdit}
                         onChange={e => patch(row, { fixed_date: e.target.value || null })} />
                : (shortDate(row.fixed_date) || <span className="bz-muted">—</span>)}
            </td>
            <td title={row.counterparty}>
              {editable
                ? <EditableText value={row.counterparty} disabled={!canEdit} placeholder="EPC · O&M"
                                onSave={v => patch(row, { counterparty: v })} />
                : row.counterparty}
            </td>
            {canEdit && editable && (
              <td>
                <button className="btn-ghost" style={{ padding: 3 }} onClick={() => remove(row)}
                        aria-label="삭제"><Trash2 size={13} /></button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  )

  return (
    <div className="card block" id={id}>
      <SectionHead title="하자 보수 현황" updatedAt={lastEdited(defects.map(d => d.updated_at))}
                   canEdit={canEdit} onEdit={() => setEditing(true)}
                   extra={open > 0
                     ? <span className="bz-chip" style={{ background: 'var(--amber-soft)', color: 'var(--amber)' }}>
                         미완료 {open}
                       </span>
                     : undefined} />
      <div className="bz-scroll bz-scroll-pair">{table(false)}</div>

      {editing && (
        <SectionModal title="하자 보수 현황" hint="발생부터 조치까지 남깁니다"
                      onClose={() => { setEditing(false); onChanged() }}>
          {canEdit && (
            <button className="btn-ghost" style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}
                    onClick={add} disabled={busy}><Plus size={13} /> 하자 추가</button>
          )}
          {table(true)}
        </SectionModal>
      )}
    </div>
  )
}
