import { useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { apiSend } from '../api'
import { CERTAINTY_META, EVENT_TYPES } from '../constants'
import SectionModal from './SectionModal'
import Lines from './Lines'
import { CertaintyCell, EditableSelect, EditableText } from './editors'
import type { SiteEvent } from '../types'

// 진행경과 및 이슈 — 양식 §6.
// 일자를 비우면 "진행 중"으로 표시된다(양식에 실제로 그런 행이 있다).
export default function EventSection({ siteId, events, canEdit, onChanged, onError }: {
  siteId: string
  events: SiteEvent[]
  canEdit: boolean
  onChanged: () => void
  onError: (msg: string) => void
}) {
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState(false)

  const patch = async (row: SiteEvent, body: Record<string, unknown>) => {
    await apiSend('PATCH', `/api/bizdev/events/${row.id}/`, body)
    onChanged()
  }

  const add = async () => {
    setAdding(true)
    try {
      await apiSend('POST', '/api/bizdev/events/', {
        site: siteId, event_type: 'etc', summary: '', certainty: 'unconfirmed',
        event_date: new Date().toISOString().slice(0, 10),
      })
      onChanged()
    } catch (e) {
      onError(e instanceof Error ? e.message : '경과 추가 실패')
    } finally {
      setAdding(false)
    }
  }

  const remove = async (row: SiteEvent) => {
    if (!confirm('이 항목을 삭제할까요?')) return
    try {
      await apiSend('DELETE', `/api/bizdev/events/${row.id}/`)
      onChanged()
    } catch (e) {
      onError(e instanceof Error ? e.message : '삭제 실패')
    }
  }

  const ongoing = events.filter(e => e.is_ongoing).length

  const header = (
      <div className="bz-sec-head">
        <h3>6. 진행경과 및 이슈</h3>
        <div className="bz-sec-actions">
          {ongoing > 0 && (
            <span className="bz-chip" style={{ background: 'var(--amber-soft)', color: 'var(--amber)' }}>
              진행 중 {ongoing}
            </span>
          )}
          {canEdit && (
            <button className="btn-ghost bz-edit-btn" onClick={() => setEditing(true)}>
              <Pencil size={13} /> 편집
            </button>
          )}
        </div>
      </div>
  )

  const table = (editable: boolean) => (
      <table className="tbl bz-doc-tbl" style={{ marginTop: 10 }}>
        <thead>
          <tr>
            <th style={{ width: 130 }}>일자</th>
            <th style={{ width: 100 }}>유형</th>
            <th>주요 내용</th>
            <th style={{ width: 90 }}>확정도</th>
            {canEdit && editable && <th style={{ width: 34 }} />}
          </tr>
        </thead>
        <tbody>
          {events.length === 0 && (
            <tr><td colSpan={canEdit && editable ? 5 : 4} style={{ textAlign: 'center', color: 'var(--ink-faint)', fontSize: 12 }}>
              등록된 경과가 없습니다.
            </td></tr>
          )}
          {events.map(row => (
            <tr key={row.id}>
              <td>
                {editable ? (
                  <input className="bz-cell-input" type="date" value={row.event_date || ''}
                         disabled={!canEdit}
                         onChange={e => patch(row, { event_date: e.target.value || null })} />
                ) : (
                  <span>{row.event_date || ''}</span>
                )}
                {row.is_ongoing && (
                  <span className="bz-chip" style={{ background: 'var(--amber-soft)', color: 'var(--amber)' }}>
                    진행 중
                  </span>
                )}
              </td>
              <td>
                {editable
                  ? <EditableSelect value={row.event_type} options={EVENT_TYPES} disabled={!canEdit}
                                    onSave={v => patch(row, { event_type: v })} />
                  : <span>{row.type_label}</span>}
              </td>
              <td>
                {editable
                  ? <EditableText value={row.summary} multiline disabled={!canEdit}
                                  onSave={v => patch(row, { summary: v })} />
                  : <Lines text={row.summary} />}
              </td>
              <td>
                {editable ? (
                  <CertaintyCell value={row.certainty} disabled={!canEdit}
                                 onSave={v => patch(row, { certainty: v })} />
                ) : (
                  <span className="bz-chip" style={{
                    background: `color-mix(in srgb, ${CERTAINTY_META[row.certainty].color} 12%, transparent)`,
                    color: CERTAINTY_META[row.certainty].color,
                  }}>{CERTAINTY_META[row.certainty].label}</span>
                )}
              </td>
              {canEdit && editable && (
                <td>
                  <button className="btn-ghost" style={{ padding: 3 }} onClick={() => remove(row)} aria-label="삭제">
                    <Trash2 size={13} />
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
  )

  return (
    <div className="card block">
      {header}
      {table(false)}
      {editing && (
        <SectionModal title="6. 진행경과 및 이슈"
                      hint='일자를 비우면 "진행 중"으로 표시됩니다'
                      onClose={() => { setEditing(false); onChanged() }}>
          {canEdit && (
            <button className="btn-ghost" style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}
                    onClick={add} disabled={adding}>
              <Plus size={13} /> 경과 추가
            </button>
          )}
          {table(true)}
        </SectionModal>
      )}
    </div>
  )
}
