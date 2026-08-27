import { ExternalLink } from 'lucide-react'
import type { Law } from './types'

const CAT_COLOR: Record<string, string> = {
  입법예고: 'var(--amber)',
  개정: 'var(--brand)',
  시행: 'var(--green-accent)',
  기타: 'var(--ink-faint)',
}

// 전체 영향 법령 동향 상위 3 — 원본 index.page.js 법령 레일 이식
export default function LawRail({ laws }: { laws: Law[] }) {
  return (
    <div className="card block" style={{ padding: 16 }}>
      <h3 style={{ fontSize: 13.5 }}>영향 법령 동향</h3>
      <div className="h-sub" style={{ marginBottom: 10 }}>법제처 국가법령정보 · 최근 순</div>
      {laws.length === 0 && <p className="note">데이터 없음</p>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {laws.slice(0, 3).map(l => (
          <a key={l.id} href={l.source_url || undefined} target="_blank" rel="noreferrer"
             style={{ display: 'flex', gap: 8, textDecoration: 'none', color: 'inherit', alignItems: 'flex-start' }}>
            <span className="bz-chip" style={{
              background: `color-mix(in srgb, ${CAT_COLOR[l.category] || 'var(--ink-faint)'} 14%, transparent)`,
              color: CAT_COLOR[l.category] || 'var(--ink-faint)', flexShrink: 0,
            }}>{l.category}</span>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 500, lineHeight: 1.35 }}>
                {l.short_name || l.law_name} <ExternalLink size={10} style={{ display: 'inline', verticalAlign: '-1px', color: 'var(--ink-faint)' }} />
              </div>
              <div style={{ fontSize: 10.5, color: 'var(--ink-faint)', marginTop: 2 }}>
                {l.ministry}{l.date ? ` · ${l.date}` : ''}
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  )
}
