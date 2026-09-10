import { useState } from 'react'
import { Paperclip } from 'lucide-react'
import BudgetEditModal from './BudgetEditModal'
import SectionHead, { lastEdited } from './SectionHead'
import { BUDGET_CATS, formatKRW, shortDate } from '../constants'
import type { BudgetApproval, BudgetEntry, BudgetSummary } from '../types'

// 예산 승인 · 집행 — 보기 전용(그래프 2개 + 집행 목록).
// 편집은 [편집] 팝업에서 승인 내역 / 집행 내역 두 부분으로 나눠 한다.
// 그래프에는 제목을 붙였다 — 예전에는 막대 두 개만 있어 무엇을 뜻하는지 알 수 없었다.
export default function BudgetCard({ siteId, entries, approvals, summary, canEdit, onChanged }: {
  siteId: string
  entries: BudgetEntry[]
  approvals: BudgetApproval[]
  summary: BudgetSummary
  canEdit: boolean
  onChanged: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [tab, setTab] = useState<'approval' | 'entry'>('entry')
  const approved = summary.approved || 0
  const executed = summary.total || 0
  const over = approved > 0 && executed > approved
  const execPct = Math.min(100, summary.exec_pct)

  const cats = BUDGET_CATS.map(c => ({ ...c, amount: summary.by_category?.[c.key] || 0 }))
                          .filter(c => c.amount > 0)

  const updatedAt = lastEdited([
    ...entries.map(e => e.updated_at), ...approvals.map(a => a.updated_at),
  ])

  return (
    <div className="card block">
      <SectionHead title="예산 승인 · 집행" updatedAt={updatedAt} canEdit={canEdit}
                   onEdit={() => setEditing(true)} />
      <div className="bz-scroll bz-scroll-pair">
      <div className="h-sub">
        집행 {formatKRW(executed)} / 승인 {formatKRW(approved)} · 집행률 {summary.exec_pct}%
      </div>

      {/* 그래프 1 — 승인 예산 대비 집행 */}
      <div className="bz-chart">
        <div className="bz-chart-head">
          <span className="bz-chart-title">승인 예산 대비 집행</span>
          <span className="bz-chart-note">
            {over ? '승인 초과' : `잔액 ${formatKRW(approved - executed)}`}
          </span>
        </div>
        <div className="bz-bar" style={{ height: 12 }}>
          <div className="bz-bar-fill" style={{
            width: `${execPct}%`, background: over ? 'var(--red)' : 'var(--brand)',
          }} />
        </div>
        <div className="bz-chart-axis">
          <span>집행 {formatKRW(executed)}</span>
          <span>승인 {formatKRW(approved)}</span>
        </div>
        {over && (
          <p className="note" style={{ color: 'var(--red)', marginTop: 4, fontWeight: 600 }}>
            ⚠ 집행액이 승인 예산을 초과했습니다
          </p>
        )}
      </div>

      {/* 그래프 2 — 용도별 집행 구성 */}
      <div className="bz-chart">
        <div className="bz-chart-head">
          <span className="bz-chart-title">용도별 집행 구성</span>
          <span className="bz-chart-note">집행액 {formatKRW(executed)} 기준</span>
        </div>
        {cats.length === 0 ? (
          <p className="note">집행 내역이 없습니다.</p>
        ) : (
          <>
            <div className="bz-stackbar">
              {cats.map(c => (
                <div key={c.key} title={`${c.label} ${formatKRW(c.amount)}`}
                     style={{ width: `${(c.amount / executed) * 100}%`, background: c.color }} />
              ))}
            </div>
            <div className="bz-legend">
              {cats.map(c => (
                <span key={c.key} className="bz-legend-item">
                  <span className="bz-budget-dot" style={{ background: c.color }} />
                  {c.label} {formatKRW(c.amount)}
                  <span className="bz-muted"> ({Math.round((c.amount / executed) * 100)}%)</span>
                </span>
              ))}
            </div>
          </>
        )}
      </div>

      {/* 내역 — 승인 예산 / 집행 실적 전환 */}
      <div className="bz-minitabs">
        <button className={`bz-minitab ${tab === 'approval' ? 'on' : ''}`}
                onClick={() => setTab('approval')}>
          승인 예산 <span className="bz-muted">{approvals.length}</span>
        </button>
        <button className={`bz-minitab ${tab === 'entry' ? 'on' : ''}`}
                onClick={() => setTab('entry')}>
          집행 실적 <span className="bz-muted">{entries.length}</span>
        </button>
      </div>

      {tab === 'approval' ? (
        <table className="tbl bz-doc-tbl bz-budget-tbl approval">
          <thead>
            <tr>
              <th>용도</th>
              <th>승인액</th>
              <th>승인일</th>
              <th>적요</th>
            </tr>
          </thead>
          <tbody>
            {approvals.length === 0 && (
              <tr><td colSpan={4} className="bz-empty">승인 내역이 없습니다.</td></tr>
            )}
            {approvals.map(a => {
              const cat = BUDGET_CATS.find(c => c.key === a.category)
              return (
                <tr key={a.id}>
                  <td>
                    <span className="bz-chip" style={{ background: `${cat?.color}1c`, color: cat?.color }}>
                      {cat?.label}
                    </span>
                  </td>
                  <td className="bz-num bz-nowrap">{formatKRW(a.amount_krw)}</td>
                  <td className="bz-nowrap">{shortDate(a.approved_date) || <span className="bz-muted">—</span>}</td>
                  <td title={a.memo}>{a.memo || <span className="bz-muted">—</span>}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      ) : (
        <table className="tbl bz-doc-tbl bz-budget-tbl entry">
          <thead>
            <tr>
              <th>용도</th>
              <th>금액</th>
              <th>집행일</th>
              <th>상대방</th>
              <th>적요</th>
              <th>증빙</th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 && (
              <tr><td colSpan={6} className="bz-empty">집행 내역이 없습니다.</td></tr>
            )}
            {entries.map(e => {
              const cat = BUDGET_CATS.find(c => c.key === e.category)
              return (
                <tr key={e.id}>
                  <td>
                    <span className="bz-chip" style={{ background: `${cat?.color}1c`, color: cat?.color }}>
                      {cat?.label}
                    </span>
                  </td>
                  <td className="bz-num bz-nowrap">{formatKRW(e.amount_krw)}</td>
                  <td className="bz-nowrap">{shortDate(e.exec_date)}</td>
                  <td className="bz-nowrap" title={e.payee}>{e.payee || <span className="bz-muted">—</span>}</td>
                  <td title={e.memo}>{e.memo || <span className="bz-muted">—</span>}</td>
                  <td>
                    {e.has_receipt ? (
                      <a href={`/api/bizdev/budget-entries/${e.id}/receipt/`} target="_blank"
                         rel="noreferrer" title={e.receipt_name} style={{ color: 'var(--green-accent)' }}>
                        <Paperclip size={13} />
                      </a>
                    ) : <span className="bz-muted">—</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
      </div>

      {editing && (
        <BudgetEditModal siteId={siteId} entries={entries} approvals={approvals}
                         canEdit={canEdit} onChanged={onChanged}
                         onClose={() => { setEditing(false); onChanged() }} />
      )}
    </div>
  )
}
