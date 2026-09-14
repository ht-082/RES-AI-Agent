import SectionHead from './detail/SectionHead'
import type { Law } from './types'

// 전체 영향 법령 동향 — 원본 index.page.js renderLaws 배치 그대로.
//   [분류 배지] 법령명 / 소관부처 · 일자, 상위 3건, 행 사이 구분선, 행 전체가 링크.
// 배지 색도 원본 LAW_BADGE 를 따른다(입법예고 amber · 시행 emerald ·
// 개정 blue · 기타 slate). 원본은 사내 상세 화면(policy-detail.html)으로 갔지만
// 그 화면이 아직 없어 법제처 원문(source_url)으로 연결한다.
const BADGE: Record<string, { bg: string; fg: string }> = {
  입법예고: { bg: '#fef3c7', fg: '#b45309' },
  시행: { bg: '#d1fae5', fg: '#047857' },
  개정: { bg: '#dbeafe', fg: '#1d4ed8' },
  기타: { bg: '#f1f5f9', fg: 'var(--ink-2)' },
}

export default function LawRail({ laws }: { laws: Law[] }) {
  const top = laws.slice(0, 3)

  return (
    <div className="card block">
      <SectionHead title="전체 영향 법령 동향"
                   extra={<span className="bz-law-tag">법령</span>} />
      {top.length === 0 ? (
        <p className="bz-law-empty">동향 없음</p>
      ) : (
        <div className="bz-law-list">
          {top.map(l => {
            const badge = BADGE[l.category] || BADGE['기타']
            return (
              <a key={l.id} className="bz-law-item"
                 href={l.source_url || undefined} target="_blank" rel="noreferrer">
                <span className="bz-law-badge"
                      style={{ background: badge.bg, color: badge.fg }}>{l.category}</span>
                <div className="bz-law-body">
                  <p className="bz-law-name">{l.short_name || l.law_name}</p>
                  <div className="bz-law-meta">
                    {l.ministry || ''}{l.date ? ` · ${l.date}` : ''}
                  </div>
                </div>
              </a>
            )
          })}
        </div>
      )}
    </div>
  )
}
