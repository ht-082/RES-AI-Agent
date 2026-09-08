import { useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { apiSend } from '../api'
import { EVENT_STATUSES, EVENT_STATUS_META, EVENT_TYPES, shortDate } from '../constants'
import SectionModal from './SectionModal'
import { lastEdited } from './SectionHead'
import Lines from './Lines'
import { EditableSelect, EditableText } from './editors'
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
        site: siteId, event_type: 'etc', status: 'ongoing', summary: '',
        certainty: 'unconfirmed', event_date: new Date().toISOString().slice(0, 10),
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

  const ongoing = events.filter(e => e.status === 'ongoing').length

  const header = (
      <div className="bz-sec-head">
        <h3>진행경과 및 이슈</h3>
        <div className="bz-sec-actions">
          {ongoing > 0 && (
            <span className="bz-chip" style={{ background: 'var(--amber-soft)', color: 'var(--amber)' }}>
              진행 중 {ongoing}
            </span>
          )}
          <span className="bz-updated">{lastEdited(events.map(e => e.updated_at))}</span>
          {canEdit && (
            <button className="btn-ghost bz-edit-btn" onClick={() => setEditing(true)}>
              <Pencil size={13} /> 상세내용 확인 및 편집
            </button>
          )}
        </div>
      </div>
  )

  // 보기 화면 — 표 대신 날짜 축 타임라인.
  // 시간 순 데이터라 격자보다 축이 읽기 쉽다(원본 이슈 카드도 타임라인이었다).
  const timeline = (
    <div className="bz-timeline" style={{ marginTop: 10 }}>
      {events.length === 0 && <p className="note">등록된 경과가 없습니다.</p>}
      {events.map(row => {
        const st = EVENT_STATUS_META[row.status]
        return (
          <div key={row.id} className="bz-tl-item">
            <span className="bz-tl-dot" style={{ background: st?.color }} />
            <div className="bz-tl-body">
              <div className="bz-tl-head">
                <span className="bz-tl-date">
                  {shortDate(row.event_date) || '진행 중'}
                </span>
                <span className="bz-tl-type">{row.type_label}</span>
                <span className="bz-chip" style={{
                  background: `color-mix(in srgb, ${st?.color} 12%, transparent)`, color: st?.color,
                }}>{row.status_label}</span>
              </div>
              <div className="bz-tl-text"><Lines text={row.summary} /></div>
            </div>
          </div>
        )
      })}
    </div>
  )

  const table = (editable: boolean) => (
      <table className={`tbl bz-doc-tbl bz-event-tbl ${editable ? "wide" : ""}`} style={{ marginTop: 10 }}>
        <thead>
          <tr>
            <th>등록 일자</th>
            <th>유형</th>
            <th>현황</th>
            <th>주요 내용</th>
            {canEdit && editable && <th style={{ width: 32 }} />}
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
              <td className="bz-nowrap">
                {editable ? (
                  <input className="bz-cell-input" type="date" value={row.event_date || ''}
                         disabled={!canEdit}
                         onChange={e => patch(row, { event_date: e.target.value || null })} />
                ) : (
                  <span>{shortDate(row.event_date) || <span className="bz-muted">—</span>}</span>
                )}
              </td>
              <td>
                {editable
                  ? <EditableSelect value={row.event_type} options={EVENT_TYPES} disabled={!canEdit}
                                    onSave={v => patch(row, { event_type: v })} />
                  : <span>{row.type_label}</span>}
              </td>
              <td>
                {editable ? (
                  <EditableSelect value={row.status} options={EVENT_STATUSES} disabled={!canEdit}
                                  onSave={v => patch(row, { status: v })}
                                  style={{
                                    color: EVENT_STATUS_META[row.status]?.color, fontWeight: 700,
                                    fontSize: 11, borderRadius: 6, textAlign: 'center',
                                    background: `color-mix(in srgb, ${EVENT_STATUS_META[row.status]?.color} 12%, transparent)`,
                                  }} />
                ) : (
                  <span className="bz-chip" style={{
                    background: `color-mix(in srgb, ${EVENT_STATUS_META[row.status]?.color} 12%, transparent)`,
                    color: EVENT_STATUS_META[row.status]?.color,
                  }}>{row.status_label}</span>
                )}
              </td>
              <td>
                {editable
                  ? <EditableText value={row.summary} multiline disabled={!canEdit}
                                  onSave={v => patch(row, { summary: v })} />
                  : <Lines text={row.summary} />}
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
      {timeline}
      {editing && (
        <SectionModal title="진행경과 및 이슈"
                      hint='등록 일자와 현황(진행중·보류·완료)을 함께 관리합니다'
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
