import { useState } from 'react'
import { Paperclip, Trash2 } from 'lucide-react'
import { apiSend, apiUpload } from '../api'
import { BUDGET_CATS, formatKRW, formatWonExact } from '../constants'
import type { BudgetEntry, BudgetSummary } from '../types'

// 예산 승인·집행 — 원본 project.html 카드3 (CRUD + 증빙 + 용도별 스택바 + 초과 경고)
export default function BudgetCard({ siteId, entries, summary, canEdit, onChanged }: {
  siteId: string
  entries: BudgetEntry[]
  summary: BudgetSummary
  canEdit: boolean
  onChanged: () => void
}) {
  const [f, setF] = useState({ category: 'land', amount: '', exec_date: new Date().toISOString().slice(0, 10), memo: '' })
  const [receipt, setReceipt] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const over = summary.approved > 0 && summary.total > summary.approved
  const execPct = Math.min(100, summary.exec_pct)

  const add = async () => {
    const amount = parseInt(f.amount.replace(/[^0-9]/g, '') || '0', 10)
    if (amount <= 0) { setError('금액을 입력하세요.'); return }
    setBusy(true); setError('')
    try {
      const form = new FormData()
      form.append('site', siteId)
      form.append('category', f.category)
      form.append('amount_krw', String(amount))
      form.append('exec_date', f.exec_date)
      form.append('memo', f.memo)
      if (receipt) form.append('receipt', receipt)
      await apiUpload('/api/bizdev/budget-entries/', form)
      setF({ category: 'land', amount: '', exec_date: new Date().toISOString().slice(0, 10), memo: '' })
      setReceipt(null)
      onChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : '등록 실패')
    } finally {
      setBusy(false)
    }
  }

  const remove = async (id: string) => {
    if (!confirm('이 집행 내역을 삭제할까요?')) return
    try {
      await apiSend('DELETE', `/api/bizdev/budget-entries/${id}/`)
      onChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : '삭제 실패')
    }
  }

  return (
    <div className="card block">
      <h3>예산 승인 · 집행</h3>
      <div className="h-sub" style={{ marginBottom: 12 }}>
        집행 {formatKRW(summary.total)} / 승인 {formatKRW(summary.approved)} · 집행률 {summary.exec_pct}%
      </div>

      <div className="bz-bar" style={{ height: 12 }}>
        <div className="bz-bar-fill" style={{ width: `${execPct}%`, background: over ? 'var(--red)' : 'var(--brand)' }} />
      </div>
      {over && (
        <p style={{ color: 'var(--red)', fontSize: 12, marginTop: 6, fontWeight: 600 }}>
          ⚠ 집행액이 승인 예산을 초과했습니다
        </p>
      )}

      {/* 용도별 스택바 */}
      <div style={{ marginTop: 14 }}>
        <div style={{ display: 'flex', height: 10, borderRadius: 6, overflow: 'hidden', background: 'var(--surface-2)' }}>
          {BUDGET_CATS.map(c => {
            const v = summary.by_category[c.key] || 0
            if (!v || !summary.total) return null
            return <div key={c.key} title={`${c.label} ${formatKRW(v)}`}
                        style={{ width: `${(v / summary.total) * 100}%`, background: c.color }} />
          })}
        </div>
        <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 11, color: 'var(--ink-soft)', flexWrap: 'wrap' }}>
          {BUDGET_CATS.map(c => {
            const v = summary.by_category[c.key] || 0
            return (
              <span key={c.key} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: c.color }} />
                {c.label} {formatKRW(v)}{summary.total ? ` (${Math.round((v / summary.total) * 100)}%)` : ''}
              </span>
            )
          })}
        </div>
      </div>

      {/* 입력 폼 */}
      {canEdit && (
        <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap', alignItems: 'center' }}>
          <select className="inp" style={{ width: 90 }} value={f.category}
                  onChange={e => setF({ ...f, category: e.target.value })}>
            {BUDGET_CATS.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
          </select>
          <input className="inp" style={{ width: 130 }} placeholder="금액(원)" value={f.amount}
                 onChange={e => setF({ ...f, amount: e.target.value })} />
          <input className="inp" style={{ width: 140 }} type="date" value={f.exec_date}
                 onChange={e => setF({ ...f, exec_date: e.target.value })} />
          <input className="inp" style={{ flex: 1, minWidth: 120 }} placeholder="적요" value={f.memo}
                 onChange={e => setF({ ...f, memo: e.target.value })} />
          <label className="btn-ghost" style={{ cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
            <Paperclip size={13} /> {receipt ? receipt.name.slice(0, 12) : '증빙'}
            <input type="file" style={{ display: 'none' }}
                   onChange={e => setReceipt(e.target.files?.[0] || null)} />
          </label>
          <button className="btn-primary" onClick={add} disabled={busy}>등록</button>
        </div>
      )}
      {error && <p className="note" style={{ color: 'var(--red)', marginTop: 8 }}>{error}</p>}

      {/* 내역 */}
      <table className="tbl" style={{ marginTop: 12 }}>
        <thead>
          <tr><th>용도</th><th>금액</th><th>집행일</th><th>적요</th><th style={{ width: 80 }}></th></tr>
        </thead>
        <tbody>
          {entries.length === 0 && (
            <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--ink-faint)', fontSize: 12 }}>집행 내역이 없습니다.</td></tr>
          )}
          {entries.map(en => {
            const cat = BUDGET_CATS.find(c => c.key === en.category)
            return (
              <tr key={en.id}>
                <td>
                  <span className="bz-chip" style={{ background: `${cat?.color}1c`, color: cat?.color }}>{cat?.label}</span>
                </td>
                <td style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>{formatWonExact(en.amount_krw)}</td>
                <td style={{ fontSize: 12 }}>{en.exec_date}</td>
                <td style={{ fontSize: 12 }}>{en.memo}</td>
                <td style={{ textAlign: 'right' }}>
                  {en.has_receipt && (
                    <a href={`/api/bizdev/budget-entries/${en.id}/receipt/`} target="_blank" rel="noreferrer"
                       title={en.receipt_name} style={{ marginRight: 8, color: 'var(--green-accent)' }}>
                      <Paperclip size={14} style={{ verticalAlign: '-2px' }} />
                    </a>
                  )}
                  {canEdit && (
                    <button className="btn-ghost" style={{ padding: 3 }} onClick={() => remove(en.id)} aria-label="삭제">
                      <Trash2 size={14} />
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
