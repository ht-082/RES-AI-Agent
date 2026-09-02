import { useRef, useState } from 'react'
import { Paperclip, Plus, Trash2, X } from 'lucide-react'
import SectionModal from './SectionModal'
import { EditableSelect, EditableText } from './editors'
import { apiSend, apiUpload } from '../api'
import { BUDGET_CATS, formatKRW } from '../constants'
import type { BudgetApproval, BudgetEntry } from '../types'

const CAT_OPTIONS: Array<[string, string]> = BUDGET_CATS.map(c => [c.key, c.label])
const won = (v: string) => parseInt((v || '').replace(/[^0-9]/g, '') || '0', 10)

// 예산 편집 — 승인 내역 / 집행 내역 두 부분.
// 승인도 용도별 항목으로 쌓고, 집행은 그 용도에 대응해 기록한다.
export default function BudgetEditModal({ siteId, entries, approvals, canEdit, onChanged, onClose }: {
  siteId: string
  entries: BudgetEntry[]
  approvals: BudgetApproval[]
  canEdit: boolean
  onChanged: () => void
  onClose: () => void
}) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  // 증빙은 집행 항목마다 따로 붙인다 — 어느 행에 붙일지 눌린 행을 기억해 둔다
  const receiptTarget = useRef<string | null>(null)
  const receiptInput = useRef<HTMLInputElement>(null)

  const fail = (e: unknown, fb: string) => setError(e instanceof Error ? e.message : fb)

  // ── 승인 내역 ─────────────────────────────────────────────
  const patchApproval = async (row: BudgetApproval, body: Record<string, unknown>) => {
    await apiSend('PATCH', `/api/bizdev/budget-approvals/${row.id}/`, body)
    onChanged()
  }
  const addApproval = async () => {
    setBusy(true)
    try {
      await apiSend('POST', '/api/bizdev/budget-approvals/', {
        site: siteId, category: 'land', amount_krw: 1, memo: '',
        approved_date: new Date().toISOString().slice(0, 10),
      })
      onChanged()
    } catch (e) { fail(e, '승인 항목 추가 실패') } finally { setBusy(false) }
  }
  const removeApproval = async (row: BudgetApproval) => {
    if (!confirm(`${row.category_label} 승인 ${formatKRW(row.amount_krw)}을 삭제할까요?`)) return
    try {
      await apiSend('DELETE', `/api/bizdev/budget-approvals/${row.id}/`)
      onChanged()
    } catch (e) { fail(e, '삭제 실패') }
  }

  // ── 집행 내역 ─────────────────────────────────────────────
  const patchEntry = async (row: BudgetEntry, body: Record<string, unknown>) => {
    await apiSend('PATCH', `/api/bizdev/budget-entries/${row.id}/`, body)
    onChanged()
  }
  const addEntry = async () => {
    setBusy(true)
    try {
      const form = new FormData()
      form.append('site', siteId)
      form.append('category', 'land')
      form.append('amount_krw', '1')
      form.append('exec_date', new Date().toISOString().slice(0, 10))
      form.append('payee', '')
      form.append('memo', '')
      await apiUpload('/api/bizdev/budget-entries/', form)
      onChanged()
    } catch (e) { fail(e, '집행 내역 추가 실패') } finally { setBusy(false) }
  }
  const attachReceipt = async (file: File | undefined) => {
    const id = receiptTarget.current
    if (!file || !id) return
    const form = new FormData()
    form.append('receipt', file)
    try {
      await apiUpload(`/api/bizdev/budget-entries/${id}/`, form, 'PATCH')
      onChanged()
    } catch (e) { fail(e, '증빙 첨부 실패') }
    if (receiptInput.current) receiptInput.current.value = ''
  }
  const detachReceipt = async (row: BudgetEntry) => {
    if (!confirm(`증빙 "${row.receipt_name}"을 떼어 낼까요?`)) return
    try {
      await apiSend('DELETE', `/api/bizdev/budget-entries/${row.id}/receipt-file/`)
      onChanged()
    } catch (e) { fail(e, '증빙 삭제 실패') }
  }

  const removeEntry = async (row: BudgetEntry) => {
    if (!confirm('이 집행 내역을 삭제할까요?')) return
    try {
      await apiSend('DELETE', `/api/bizdev/budget-entries/${row.id}/`)
      onChanged()
    } catch (e) { fail(e, '삭제 실패') }
  }

  // 용도별 승인/집행 대비 — 집행 입력 시 남은 예산을 옆에 보여 준다
  const approvedOf = (cat: string) =>
    approvals.filter(a => a.category === cat).reduce((s, a) => s + a.amount_krw, 0)
  const executedOf = (cat: string) =>
    entries.filter(e => e.category === cat).reduce((s, e) => s + e.amount_krw, 0)

  return (
    <SectionModal title="예산 승인 · 집행" hint="고친 내용은 자동 저장됩니다" onClose={onClose}>
      {error && <p className="note" style={{ color: 'var(--red)' }}>{error}</p>}

      {/* 1부 — 승인 내역 */}
      <div className="bz-block-title" style={{ justifyContent: 'space-between' }}>
        <span>1. 예산 승인 내역</span>
        {canEdit && (
          <button className="btn-ghost bz-edit-btn" onClick={addApproval} disabled={busy}>
            <Plus size={13} /> 승인 항목 추가
          </button>
        )}
      </div>
      <table className="tbl bz-doc-tbl">
        <thead>
          <tr>
            <th style={{ width: 96 }}>용도</th>
            <th style={{ width: 130 }}>승인액(원)</th>
            <th style={{ width: 130 }}>승인일</th>
            <th>적요</th>
            {canEdit && <th style={{ width: 34 }} />}
          </tr>
        </thead>
        <tbody>
          {approvals.length === 0 && (
            <tr><td colSpan={canEdit ? 5 : 4} className="bz-empty">승인 내역이 없습니다.</td></tr>
          )}
          {approvals.map(row => (
            <tr key={row.id}>
              <td>
                <EditableSelect value={row.category} options={CAT_OPTIONS} disabled={!canEdit}
                                onSave={v => patchApproval(row, { category: v })} />
              </td>
              <td>
                <EditableText value={String(row.amount_krw)} disabled={!canEdit}
                              onSave={v => patchApproval(row, { amount_krw: won(v) || 1 })} />
                <div className="bz-hint">{formatKRW(row.amount_krw)}</div>
              </td>
              <td>
                <input className="bz-cell-input" type="date" value={row.approved_date || ''}
                       disabled={!canEdit}
                       onChange={e => patchApproval(row, { approved_date: e.target.value || null })} />
              </td>
              <td>
                <EditableText value={row.memo} placeholder="—" disabled={!canEdit}
                              onSave={v => patchApproval(row, { memo: v })} />
              </td>
              {canEdit && (
                <td>
                  <button className="btn-ghost" style={{ padding: 3 }} aria-label="삭제"
                          onClick={() => removeApproval(row)}><Trash2 size={13} /></button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {/* 2부 — 집행 내역 */}
      <div className="bz-block-title" style={{ justifyContent: 'space-between', marginTop: 20 }}>
        <span>2. 예산 집행 내역</span>
        {canEdit && (
          <button className="btn-ghost bz-edit-btn" onClick={addEntry} disabled={busy}>
            <Plus size={13} /> 집행 추가
          </button>
        )}
      </div>
      <input ref={receiptInput} type="file" style={{ display: 'none' }}
             onChange={e => attachReceipt(e.target.files?.[0])} />
      <table className="tbl bz-doc-tbl">
        <thead>
          <tr>
            <th style={{ width: 96 }}>용도</th>
            <th style={{ width: 120 }}>집행액(원)</th>
            <th style={{ width: 124 }}>집행일</th>
            <th style={{ width: 120 }}>상대방</th>
            <th>적요</th>
            <th style={{ width: 78 }}>증빙</th>
            {canEdit && <th style={{ width: 34 }} />}
          </tr>
        </thead>
        <tbody>
          {entries.length === 0 && (
            <tr><td colSpan={canEdit ? 7 : 6} className="bz-empty">집행 내역이 없습니다.</td></tr>
          )}
          {entries.map(row => {
            const cap = approvedOf(row.category)
            const used = executedOf(row.category)
            return (
              <tr key={row.id}>
                <td>
                  <EditableSelect value={row.category} options={CAT_OPTIONS} disabled={!canEdit}
                                  onSave={v => patchEntry(row, { category: v })} />
                  <div className="bz-hint" style={{ color: cap && used > cap ? 'var(--red)' : undefined }}>
                    {cap ? `승인 ${formatKRW(cap)} 중 ${formatKRW(used)}` : '승인 없음'}
                  </div>
                </td>
                <td>
                  <EditableText value={String(row.amount_krw)} disabled={!canEdit}
                                onSave={v => patchEntry(row, { amount_krw: won(v) || 1 })} />
                  <div className="bz-hint">{formatKRW(row.amount_krw)}</div>
                </td>
                <td>
                  <input className="bz-cell-input" type="date" value={row.exec_date || ''}
                         disabled={!canEdit}
                         onChange={e => patchEntry(row, { exec_date: e.target.value })} />
                </td>
                <td>
                  <EditableText value={row.payee} placeholder="수취처" disabled={!canEdit}
                                onSave={v => patchEntry(row, { payee: v })} />
                </td>
                <td>
                  <EditableText value={row.memo} placeholder="—" disabled={!canEdit}
                                onSave={v => patchEntry(row, { memo: v })} />
                </td>
                <td className="bz-nowrap">
                  {row.has_receipt && (
                    <a href={`/api/bizdev/budget-entries/${row.id}/receipt/`} target="_blank"
                       rel="noreferrer" title={row.receipt_name}
                       style={{ color: 'var(--green-accent)' }}>
                      <Paperclip size={13} />
                    </a>
                  )}
                  {canEdit && (
                    <button className="btn-ghost" style={{ padding: 2 }}
                            title={row.has_receipt ? '증빙 교체' : '증빙 첨부'}
                            onClick={() => {
                              receiptTarget.current = row.id
                              receiptInput.current?.click()
                            }}>
                      {row.has_receipt ? <Paperclip size={12} /> : <Plus size={12} />}
                    </button>
                  )}
                  {canEdit && row.has_receipt && (
                    <button className="btn-ghost" style={{ padding: 2 }} title="증빙 떼기"
                            onClick={() => detachReceipt(row)}><X size={11} /></button>
                  )}
                  {!row.has_receipt && !canEdit && <span className="bz-muted">—</span>}
                </td>
                {canEdit && (
                  <td>
                    <button className="btn-ghost" style={{ padding: 3 }} aria-label="삭제"
                            onClick={() => removeEntry(row)}><Trash2 size={13} /></button>
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </SectionModal>
  )
}
