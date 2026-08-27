import { useState } from 'react'
import { Plus } from 'lucide-react'
import { apiSend } from '../api'
import { ISSUE_STATUS_META, ISSUE_TYPE_LABEL } from '../constants'
import type { CommunityIssue } from '../types'

// 지역수용성 이슈 타임라인 — 원본 project.html 카드4
export default function IssueCard({ siteId, issues, canEdit, onChanged }: {
  siteId: string
  issues: CommunityIssue[]
  canEdit: boolean
  onChanged: () => void
}) {
  const [adding, setAdding] = useState(false)
  const [f, setF] = useState({
    title: '', issue_type: 'complaint', status: 'open',
    issue_date: new Date().toISOString().slice(0, 10), description: '',
  })
  const [error, setError] = useState('')

  const add = async () => {
    if (!f.title.trim()) { setError('제목을 입력하세요.'); return }
    try {
      await apiSend('POST', '/api/bizdev/issues/', { site: siteId, ...f, title: f.title.trim() })
      setAdding(false)
      setF({ title: '', issue_type: 'complaint', status: 'open', issue_date: new Date().toISOString().slice(0, 10), description: '' })
      setError('')
      onChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : '등록 실패')
    }
  }

  const cycle = async (issue: CommunityIssue) => {
    if (!canEdit) return
    const order = ['open', 'prog', 'closed'] as const
    const next = order[(order.indexOf(issue.status) + 1) % order.length]
    try {
      await apiSend('PATCH', `/api/bizdev/issues/${issue.id}/`, { status: next })
      onChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : '변경 실패')
    }
  }

  return (
    <div className="card block">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3>지역수용성 이슈 이력</h3>
        {canEdit && (
          <button className="btn-ghost" style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}
                  onClick={() => setAdding(v => !v)}>
            <Plus size={13} /> 이슈 추가
          </button>
        )}
      </div>
      <div className="h-sub" style={{ marginBottom: 12 }}>상태 배지 클릭 → 진행중/대응중/완료 순환</div>

      {adding && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12, alignItems: 'center' }}>
          <input className="inp" style={{ flex: 1, minWidth: 160 }} placeholder="제목 *" value={f.title}
                 onChange={e => setF({ ...f, title: e.target.value })} />
          <select className="inp" style={{ width: 90 }} value={f.issue_type}
                  onChange={e => setF({ ...f, issue_type: e.target.value })}>
            <option value="complaint">민원성</option><option value="grid">계통</option><option value="etc">기타</option>
          </select>
          <input className="inp" style={{ width: 140 }} type="date" value={f.issue_date}
                 onChange={e => setF({ ...f, issue_date: e.target.value })} />
          <input className="inp" style={{ flex: 1, minWidth: 140 }} placeholder="설명" value={f.description}
                 onChange={e => setF({ ...f, description: e.target.value })} />
          <button className="btn-primary" onClick={add}>등록</button>
        </div>
      )}
      {error && <p className="note" style={{ color: 'var(--red)', marginBottom: 8 }}>{error}</p>}

      {issues.length === 0 && <p className="note">등록된 이슈가 없습니다.</p>}
      <div className="bz-timeline">
        {issues.map(issue => {
          const meta = ISSUE_STATUS_META[issue.status]
          return (
            <div key={issue.id} className="bz-tl-item">
              <span className="bz-tl-dot" style={{ background: meta.color }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 12.5, fontWeight: 600 }}>{issue.title}</span>
                  <span className="bz-chip" style={{
                    background: `color-mix(in srgb, ${meta.color} 14%, transparent)`,
                    color: meta.color, cursor: canEdit ? 'pointer' : 'default',
                  }} onClick={() => cycle(issue)}>{meta.label}</span>
                  <span style={{ fontSize: 10.5, color: 'var(--ink-faint)' }}>
                    {ISSUE_TYPE_LABEL[issue.issue_type]} · {issue.issue_date}
                  </span>
                </div>
                {issue.description && (
                  <p style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 3, lineHeight: 1.5 }}>{issue.description}</p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
