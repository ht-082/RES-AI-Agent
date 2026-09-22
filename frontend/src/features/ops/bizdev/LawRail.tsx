import { useState } from 'react'
import { Check, ExternalLink, Plus, Sparkles } from 'lucide-react'
import SectionHead from './detail/SectionHead'
import SectionModal from './detail/SectionModal'
import { apiSend } from './api'
import type { Law, LawCatalogItem, WatchedLaw } from './types'

// 전체 영향 법령 동향 — 지켜보는 법령을 위에 띄우고, 그 법(과 시행령)의
// 개정만 아래 표에 올린다. 스냅샷에는 법령 묶음이 21개 들어 있는데 전부
// 늘어놓으면 정작 우리 인허가에 걸리는 개정이 그 사이에 묻힌다.
// 법령명은 법제처 원문으로 연결한다(사내 법령 상세 화면은 2차).
// 'AI 제언'은 정해진 질문을 사내 챗봇에 넣고 그 화면으로 넘긴다 — 검색·출처·
// 이어 묻기는 챗봇이 하던 대로 한다(우리가 그 파이프라인을 복제하지 않는다).
const CAT_COLOR: Record<string, string> = {
  입법예고: 'var(--amber)',
  개정: 'var(--brand)',
  시행: 'var(--green-accent)',
  기타: 'var(--ink-faint)',
}

export default function LawRail({ laws, watched, catalog, onAdvise, busyId, onWatchedChanged }: {
  laws: Law[]
  watched: WatchedLaw[]
  catalog: LawCatalogItem[]
  onAdvise: (law: Law) => void
  busyId?: string | null
  onWatchedChanged: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [busyFamily, setBusyFamily] = useState('')
  const [error, setError] = useState('')

  const watchedOf = (family: string) => watched.find(w => w.family === family)

  // 고르는 즉시 저장한다 (다른 편집 팝업과 같은 방식 — 따로 저장 버튼 없음)
  const toggle = async (family: string) => {
    const row = watchedOf(family)
    setBusyFamily(family)
    setError('')
    try {
      if (row) await apiSend('DELETE', `/api/bizdev/watched-laws/${row.id}/`)
      else await apiSend('POST', '/api/bizdev/watched-laws/', { family })
      onWatchedChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : '저장하지 못했습니다.')
    } finally {
      setBusyFamily('')
    }
  }

  return (
    <div className="card block bz-law-card">
      <SectionHead title="전체 영향 법령 동향" canEdit onEdit={() => setEditing(true)}
                   extra={<span className="bz-chip bz-law-count">{watched.length}개 법령</span>} />

      {/* 무엇을 지켜보고 있는지 먼저 보여 준다 — 아래 표가 '전부'가 아니라
          '고른 것'임을 표에 들어가기 전에 알 수 있어야 한다. */}
      <div className="bz-law-watch">
        {watched.length === 0 ? (
          <p className="note bz-law-empty">
            지켜볼 법령이 없습니다. 오른쪽 위 편집에서 골라 주세요.
          </p>
        ) : (
          <div className="bz-chips">
            {watched.map(w => (
              <span key={w.id} className="bz-law-pill" title={w.law_name}>{w.family}</span>
            ))}
          </div>
        )}
        <div className="h-sub bz-law-note">시행령 · 시행규칙 개정도 함께 봅니다</div>
      </div>

      {/* 여섯 열이라 반폭 카드에서는 폭이 모자란다. 잘라 버리지 않고
          가로로 밀어 볼 수 있게 한다(전체 폭에서는 스크롤이 생기지 않는다). */}
      <div className="bz-law-scroll">
      <table className="tbl bz-doc-tbl bz-law-tbl">
        <thead>
          <tr>
            <th>구분</th>
            <th>법령명</th>
            <th>주관부처</th>
            <th>시행일</th>
            <th>개정 및 신설 내용</th>
            <th className="bz-law-ai-col">AI 제언</th>
          </tr>
        </thead>
        <tbody>
          {laws.length === 0 && (
            <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--ink-faint)', fontSize: 12 }}>
              {watched.length === 0 ? '고른 법령이 없습니다' : '동향 없음'}
            </td></tr>
          )}
          {laws.map(l => {
            const color = CAT_COLOR[l.category] || CAT_COLOR['기타']
            const name = l.short_name || l.law_name
            return (
              <tr key={l.id}>
                <td>
                  <span className="bz-chip" style={{
                    background: `color-mix(in srgb, ${color} 14%, transparent)`, color,
                  }}>{l.category}</span>
                </td>
                <th scope="row" title={name}>
                  {l.source_url ? (
                    <a className="bz-law-link" href={l.source_url} target="_blank" rel="noreferrer">
                      {name} <ExternalLink size={10} />
                    </a>
                  ) : name}
                </th>
                <td title={l.ministry}>{l.ministry || <span className="bz-muted">—</span>}</td>
                <td className="bz-nowrap">{l.date || <span className="bz-muted">—</span>}</td>
                <td title={l.summary || l.title}>
                  {l.summary || l.title || <span className="bz-muted">—</span>}
                </td>
                <td>
                  <button className="btn-ghost bz-law-ai" disabled={busyId === l.id}
                          onClick={() => onAdvise(l)}
                          title="이 법령이 우리 사업에 미칠 영향을 챗봇에 물어봅니다">
                    <Sparkles size={12} /> {busyId === l.id ? '여는 중' : '제언'}
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      </div>

      {editing && (
        <SectionModal title="관심 법령" onClose={() => setEditing(false)}
                      hint="고른 법령의 개정만 동향 표에 올라갑니다 (시행령 포함 · 자동 저장)">
          {error && <p className="note" style={{ color: 'var(--red)' }}>{error}</p>}
          <table className="tbl bz-doc-tbl bz-law-pick">
            <thead>
              <tr>
                <th className="bz-law-pick-act" />
                <th>법령</th>
                <th>정식 명칭</th>
                <th>주관부처</th>
                <th className="bz-nowrap">최근 개정</th>
              </tr>
            </thead>
            <tbody>
              {catalog.map(c => {
                const on = !!watchedOf(c.family)
                return (
                  <tr key={c.family} className={on ? 'bz-law-pick-on' : ''}>
                    <td>
                      <button className={on ? 'btn-primary bz-law-pick-btn' : 'btn-ghost bz-law-pick-btn'}
                              disabled={busyFamily === c.family}
                              onClick={() => toggle(c.family)}
                              title={on ? '동향에서 빼기' : '동향에 넣기'}>
                        {on ? <Check size={13} /> : <Plus size={13} />}
                      </button>
                    </td>
                    <th scope="row">{c.family}</th>
                    <td title={c.law_name}>{c.law_name}</td>
                    <td title={c.ministry}>{c.ministry || <span className="bz-muted">—</span>}</td>
                    <td className="bz-nowrap">{c.latest || <span className="bz-muted">—</span>}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </SectionModal>
      )}
    </div>
  )
}
