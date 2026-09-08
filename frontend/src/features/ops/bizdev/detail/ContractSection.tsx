import { useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { apiSend } from '../api'
import { CONTRACT_CATEGORIES, CONTRACT_STATUS_META } from '../constants'
import SectionModal from './SectionModal'
import { lastEdited } from './SectionHead'
import Lines from './Lines'
import { EditableSelect, EditableText } from './editors'
import type { Contract } from '../types'

const STATUS_OPTIONS: Array<[string, string]> = [
  ['signed', '체결'], ['planned', '체결 예정'], ['none', '미체결'],
]

// 계약 정보 — 양식 §5. 행이 계속 늘어나므로 추가·삭제가 가능하다.
export default function ContractSection({ siteId, contracts, canEdit, onChanged, onError }: {
  siteId: string
  contracts: Contract[]
  canEdit: boolean
  onChanged: () => void
  onError: (msg: string) => void
}) {
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState(false)

  const patch = async (row: Contract, body: Partial<Contract>) => {
    await apiSend('PATCH', `/api/bizdev/contracts/${row.id}/`, body)
    onChanged()
  }

  const add = async () => {
    setAdding(true)
    try {
      await apiSend('POST', '/api/bizdev/contracts/', {
        site: siteId, category: 'etc', counterparty: '', status: 'none',
        certainty: 'unconfirmed', sort_order: contracts.length,
      })
      onChanged()
    } catch (e) {
      onError(e instanceof Error ? e.message : '계약 추가 실패')
    } finally {
      setAdding(false)
    }
  }

  const remove = async (row: Contract) => {
    if (!confirm(`"${row.category_label}" 계약을 삭제할까요?`)) return
    try {
      await apiSend('DELETE', `/api/bizdev/contracts/${row.id}/`)
      onChanged()
    } catch (e) {
      onError(e instanceof Error ? e.message : '삭제 실패')
    }
  }

  const signed = contracts.filter(c => c.status === 'signed').length

  const header = (
      <div className="bz-sec-head">
        <h3>계약 정보</h3>
        <div className="bz-sec-actions">
          <span className="bz-chip" style={{ background: 'var(--mint-soft)', color: 'var(--green-600)' }}>
            체결 {signed} / {contracts.length}
          </span>
          <span className="bz-updated">{lastEdited(contracts.map(c => c.updated_at))}</span>
          {canEdit && (
            <button className="btn-ghost bz-edit-btn" onClick={() => setEditing(true)}>
              <Pencil size={13} /> 상세내용 확인 및 편집
            </button>
          )}
        </div>
      </div>
  )
  // 보기 화면 — 표 대신 목록 카드. 상대방을 앞세우고 분류는 배지로,
  // 체결 여부는 왼쪽 색 띠로 드러낸다(17종 분류가 열 너비를 잡아먹지 않는다).
  const list = (
    <div className="bz-clist">
      {contracts.length === 0 && <p className="note">등록된 계약이 없습니다.</p>}
      {contracts.map(row => {
        const st = CONTRACT_STATUS_META[row.status]
        return (
          <div key={row.id} className="bz-citem" style={{ borderLeftColor: st?.color }}>
            <div className="bz-citem-head">
              <span className="bz-citem-party">{row.counterparty || '상대방 미정'}</span>
              <span className="bz-citem-cat">{row.category_label}</span>
              <span className="bz-chip" style={{
                background: `color-mix(in srgb, ${st?.color} 12%, transparent)`, color: st?.color,
              }}>{row.status_label}</span>
            </div>
            {row.summary && (
              <div className="bz-citem-text"><Lines text={row.summary} /></div>
            )}
            {row.note && (
              <div className="bz-citem-text bz-muted"><Lines text={row.note} /></div>
            )}
          </div>
        )
      })}
    </div>
  )

  const table = (editable: boolean) => (
      <table className="tbl bz-doc-tbl bz-contract-tbl" style={{ marginTop: 10 }}>
        <thead>
          <tr>
            <th>구분</th>
            <th>상대방</th>
            <th>주요 내용</th>
            <th>체결</th>
            {canEdit && editable && <th className="bz-col-act" />}
          </tr>
        </thead>
        <tbody>
          {contracts.length === 0 && (
            <tr><td colSpan={canEdit && editable ? 5 : 4} style={{ textAlign: 'center', color: 'var(--ink-faint)', fontSize: 12 }}>
              등록된 계약이 없습니다.
            </td></tr>
          )}
          {contracts.map(row => (
            <tr key={row.id}>
              <td>
                {editable
                  ? <EditableSelect value={row.category} options={CONTRACT_CATEGORIES} disabled={!canEdit}
                                    onSave={v => patch(row, { category: v })} />
                  : <span style={{ fontWeight: 600 }} title={row.category_label}>{row.category_label}</span>}
              </td>
              <td>
                {editable
                  ? <EditableText value={row.counterparty} placeholder="미정" disabled={!canEdit}
                                  onSave={v => patch(row, { counterparty: v })} />
                  : <span title={row.counterparty}>{row.counterparty || <span className="bz-muted">미정</span>}</span>}
              </td>
              <td>
                {editable
                  ? <EditableText value={row.summary} multiline placeholder="—" disabled={!canEdit}
                                  onSave={v => patch(row, { summary: v })} />
                  : <Lines text={row.summary} />}
              </td>
              <td>
                {editable ? (
                  <EditableSelect
                    value={row.status} options={STATUS_OPTIONS} disabled={!canEdit}
                    onSave={v => patch(row, { status: v as Contract['status'] })}
                    style={{
                      color: CONTRACT_STATUS_META[row.status]?.color, fontWeight: 700, fontSize: 11,
                      background: `color-mix(in srgb, ${CONTRACT_STATUS_META[row.status]?.color} 12%, transparent)`,
                      borderRadius: 6, textAlign: 'center', width: 84,
                    }} />
                ) : (
                  <span className="bz-chip" style={{
                    background: `color-mix(in srgb, ${CONTRACT_STATUS_META[row.status]?.color} 12%, transparent)`,
                    color: CONTRACT_STATUS_META[row.status]?.color,
                  }}>{row.status_label}</span>
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
      {list}
      {editing && (
        <SectionModal title="계약 정보" hint="행을 추가·삭제하고 각 칸을 고칠 수 있습니다"
                      onClose={() => { setEditing(false); onChanged() }}>
          {canEdit && (
            <button className="btn-ghost" style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}
                    onClick={add} disabled={adding}>
              <Plus size={13} /> 계약 추가
            </button>
          )}
          {table(true)}
        </SectionModal>
      )}
    </div>
  )
}
