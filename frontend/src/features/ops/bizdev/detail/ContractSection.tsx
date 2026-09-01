import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { apiSend } from '../api'
import { CONTRACT_CATEGORIES, CONTRACT_STATUS_META } from '../constants'
import { CertaintyCell, EditableSelect, EditableText } from './editors'
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

  return (
    <div className="card block">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3>5. 계약 정보</h3>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span className="bz-chip" style={{ background: 'var(--mint-soft)', color: 'var(--green-600)' }}>
            체결 {signed} / {contracts.length}
          </span>
          {canEdit && (
            <button className="btn-ghost" style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}
                    onClick={add} disabled={adding}>
              <Plus size={13} /> 계약 추가
            </button>
          )}
        </div>
      </div>
      <table className="tbl bz-doc-tbl" style={{ marginTop: 10 }}>
        <thead>
          <tr>
            <th style={{ width: 170 }}>구분</th>
            <th style={{ width: 130 }}>상대방</th>
            <th>주요 내용</th>
            <th style={{ width: 90 }}>확정도</th>
            <th style={{ width: 96 }}>체결</th>
            {canEdit && <th style={{ width: 34 }} />}
          </tr>
        </thead>
        <tbody>
          {contracts.length === 0 && (
            <tr><td colSpan={canEdit ? 6 : 5} style={{ textAlign: 'center', color: 'var(--ink-faint)', fontSize: 12 }}>
              등록된 계약이 없습니다.
            </td></tr>
          )}
          {contracts.map(row => (
            <tr key={row.id}>
              <td>
                <EditableSelect value={row.category} options={CONTRACT_CATEGORIES} disabled={!canEdit}
                                onSave={v => patch(row, { category: v })} />
              </td>
              <td>
                <EditableText value={row.counterparty} placeholder="미정" disabled={!canEdit}
                              onSave={v => patch(row, { counterparty: v })} />
              </td>
              <td>
                <EditableText value={row.summary} multiline placeholder="—" disabled={!canEdit}
                              onSave={v => patch(row, { summary: v })} />
              </td>
              <td>
                <CertaintyCell value={row.certainty} disabled={!canEdit}
                               onSave={v => patch(row, { certainty: v as Contract['certainty'] })} />
              </td>
              <td>
                <EditableSelect
                  value={row.status} options={STATUS_OPTIONS} disabled={!canEdit}
                  onSave={v => patch(row, { status: v as Contract['status'] })}
                  style={{
                    color: CONTRACT_STATUS_META[row.status]?.color, fontWeight: 700, fontSize: 11,
                    background: `color-mix(in srgb, ${CONTRACT_STATUS_META[row.status]?.color} 12%, transparent)`,
                    borderRadius: 6, textAlign: 'center', width: 84,
                  }} />
              </td>
              {canEdit && (
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
    </div>
  )
}
