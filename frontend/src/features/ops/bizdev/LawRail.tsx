import { ExternalLink, Sparkles } from 'lucide-react'
import SectionHead from './detail/SectionHead'
import type { Law } from './types'

// 전체 영향 법령 동향 — 구분 · 법령명 · 주관부처 · 시행일 · 개정 및 신설 내용 · AI 제언.
// 법령명은 법제처 원문으로 연결한다(사내 법령 상세 화면은 2차).
const CAT_COLOR: Record<string, string> = {
  입법예고: 'var(--amber)',
  개정: 'var(--brand)',
  시행: 'var(--green-accent)',
  기타: 'var(--ink-faint)',
}

export default function LawRail({ laws }: { laws: Law[] }) {
  const top = laws.slice(0, 5)

  return (
    <div className="card block">
      <SectionHead title="전체 영향 법령 동향" />
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
          {top.length === 0 && (
            <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--ink-faint)', fontSize: 12 }}>
              동향 없음
            </td></tr>
          )}
          {top.map(l => {
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
                  {/* 법령 영향 분석(2차)이 붙으면 이 버튼이 제언을 띄운다 */}
                  <button className="btn-ghost bz-law-ai" disabled
                          title="법령 영향 분석 연동 후 사용 (준비 중)">
                    <Sparkles size={12} /> 제언
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      </div>
    </div>
  )
}
