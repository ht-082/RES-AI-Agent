import { ENERGY_META } from './constants'
import type { Site } from './types'

// 좌측 사업지 카드 리스트 — 원본 project.html 좌측 레일 이식
export default function SiteListRail({ sites, selectedId, onSelect }: {
  sites: Site[]
  selectedId: string
  onSelect: (id: string) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {sites.map(site => {
        const e = ENERGY_META[site.energy_type]
        const sel = site.id === selectedId
        return (
          <div key={site.id} className={`bz-site-card ${sel ? 'sel' : ''}`} onClick={() => onSelect(site.id)}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: e.color, flexShrink: 0 }} />
              <span style={{ fontSize: 12, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {site.name}
              </span>
              {site.lifecycle === 'ops' && (
                <span className="bz-chip" style={{ background: 'var(--mint-soft)', color: 'var(--green-600)' }}>운영</span>
              )}
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--ink-faint)', margin: '3px 0 6px' }}>
              {Math.round(Number(site.capacity_mw))}MW · {site.sido || site.location}
            </div>
            <div className="bz-bar" style={{ height: 5 }}>
              <div className="bz-bar-fill" style={{ width: `${site.overall_pct}%`, background: 'var(--green-accent)' }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
