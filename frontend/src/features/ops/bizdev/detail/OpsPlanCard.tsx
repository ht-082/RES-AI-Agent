import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { apiSend } from '../api'
import SectionHead, { lastEdited } from './SectionHead'
import SectionModal from './SectionModal'
import { EditableSelect, EditableText } from './editors'
import type { OpsPlanItem } from '../types'

const STATUS: Array<[string, string]> = [
  ['planned', '예정'], ['doing', '진행중'], ['done', '완료'], ['skip', '미실시'],
]
const COLOR: Record<string, string> = {
  planned: 'var(--ink-faint)', doing: 'var(--brand)',
  done: 'var(--green-accent)', skip: '#b8c4bd',
}
const ym = (d: string) => (d ? d.slice(0, 7).replace('-', '.') : '—')

// 정기 운영관리 계획(Monthly) — 양식 §1-3.
// 월마다 점검·정비 항목을 세워 두고 실시 여부를 남긴다.
export default function OpsPlanCard({ siteId, plans, canEdit, onChanged, onError, id }: {
  siteId: string
  plans: OpsPlanItem[]
  canEdit: boolean
  onChanged: () => void
  onError: (msg: string) => void
  id?: string
}) {
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)

  const patch = async (row: OpsPlanItem, body: Record<string, unknown>) => {
    await apiSend('PATCH', `/api/bizdev/ops-plans/${row.id}/`, body)
    onChanged()
  }
  const add = async () => {
    setBusy(true)
    try {
      const month = new Date().toISOString().slice(0, 8) + '01'
      await apiSend('POST', '/api/bizdev/ops-plans/', {
        site: siteId, month, title: '새 항목', status: 'planned',
      })
      onChanged()
    } catch (e) { onError(e instanceof Error ? e.message : '추가 실패') } finally { setBusy(false) }
  }
  const remove = async (row: OpsPlanItem) => {
    if (!confirm(`"${row.title}" 항목을 삭제할까요?`)) return
    try {
      await apiSend('DELETE', `/api/bizdev/ops-plans/${row.id}/`)
      onChanged()
    } catch (e) { onError(e instanceof Error ? e.message : '삭제 실패') }
  }

  const done = plans.filter(p => p.status === 'done').length

  const table = (editable: boolean) => (
    <table className="tbl bz-doc-tbl bz-plan-tbl">
      <thead>
        <tr>
          <th>월</th>
          <th>항목</th>
          <th>주기</th>
          <th>담당</th>
          <th>상태</th>
          <th>실시일</th>
          {canEdit && editable && <th className="bz-col-act" />}
        </tr>
      </thead>
      <tbody>
        {plans.length === 0 && (
          <tr><td colSpan={canEdit && editable ? 7 : 6}
                  style={{ textAlign: 'center', color: 'var(--ink-faint)', fontSize: 12 }}>
            등록된 계획이 없습니다.
          </td></tr>
        )}
        {plans.map(row => (
          <tr key={row.id}>
            <td className="bz-nowrap">
              {editable
                ? <input className="bz-cell-input" type="month" value={(row.month || '').slice(0, 7)}
                         disabled={!canEdit}
                         onChange={e => patch(row, { month: `${e.target.value}-01` })} />
                : ym(row.month)}
            </td>
            <td title={row.title}>
              {editable
                ? <EditableText value={row.title} disabled={!canEdit} placeholder="점검 항목"
                                onSave={v => patch(row, { title: v })} />
                : row.title}
            </td>
            <td title={row.cycle}>
              {editable
                ? <EditableText value={row.cycle} disabled={!canEdit} placeholder="월 1회"
                                onSave={v => patch(row, { cycle: v })} />
                : row.cycle}
            </td>
            <td title={row.owner}>
              {editable
                ? <EditableText value={row.owner} disabled={!canEdit} placeholder="담당"
                                onSave={v => patch(row, { owner: v })} />
                : row.owner}
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
                ? <input className="bz-cell-input" type="date" value={row.done_date || ''}
                         disabled={!canEdit}
                         onChange={e => patch(row, { done_date: e.target.value || null })} />
                : (row.done_date || <span className="bz-muted">—</span>)}
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
      <SectionHead title="정기 운영관리 계획" updatedAt={lastEdited(plans.map(p => p.updated_at))}
                   canEdit={canEdit} onEdit={() => setEditing(true)}
                   extra={plans.length > 0
                     ? <span className="bz-chip" style={{ background: 'var(--mint-soft)', color: 'var(--green-600)' }}>
                         실시 {done} / {plans.length}
                       </span>
                     : undefined} />
      <div className="bz-scroll bz-scroll-pair">{table(false)}</div>

      {editing && (
        <SectionModal title="정기 운영관리 계획" hint="월별 점검·정비 항목을 세우고 실시 여부를 남깁니다"
                      onClose={() => { setEditing(false); onChanged() }}>
          {canEdit && (
            <button className="btn-ghost" style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}
                    onClick={add} disabled={busy}><Plus size={13} /> 항목 추가</button>
          )}
          {table(true)}
        </SectionModal>
      )}
    </div>
  )
}
