import { X } from 'lucide-react'
import { ENERGY_META, STATUS_META } from './constants'
import type { Site } from './types'

// 지도 마커 클릭 시 우측 슬라이드 드로어 — 원본 index.page.js 드로어 이식.
// 주소상세(address_detail)는 표시하지 않는다(원본 비노출 정책).
export default function SiteDrawer({ site, onClose, onDetail }: {
  site: Site
  onClose: () => void
  onDetail: (site: Site) => void
}) {
  const e = ENERGY_META[site.energy_type]
  const rows: Array<[string, string]> = [
    ['설비용량', `${Math.round(Number(site.capacity_mw))} MW`],
    ['연간 예상 발전량', site.annual_gwh ? `${site.annual_gwh} GWh` : '-'],
    ['목표 COD', site.cod || '-'],
    ['전체 진척도', `${site.overall_pct}%`],
    ['담당 PM', site.pm_name || '-'],
  ]
  return (
    <div className="bz-drawer">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--ink-faint)' }}>{site.location || site.sido}</div>
          <div style={{ fontSize: 16, fontWeight: 700, marginTop: 2 }}>{site.name}</div>
        </div>
        <button className="btn-ghost" style={{ padding: 4 }} onClick={onClose} aria-label="닫기">
          <X size={16} />
        </button>
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
        <span className="bz-chip" style={{ background: `${e.color}22`, color: e.color }}>{e.label}</span>
        <span className="bz-chip" style={{ background: 'var(--mint-soft)', color: 'var(--green-600)' }}>
          {site.lifecycle === 'ops' ? '운영중' : '개발중'}
        </span>
        {site.risk_tag && (
          <span className="bz-chip" style={{ background: 'var(--red-soft)', color: 'var(--red)' }}>{site.risk_tag}</span>
        )}
      </div>
      <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {rows.map(([k, v]) => (
          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}>
            <span style={{ color: 'var(--ink-soft)' }}>{k}</span>
            <span style={{ fontWeight: 600 }}>{v}</span>
          </div>
        ))}
      </div>
      <div className="bz-bar" style={{ marginTop: 12 }}>
        <div className="bz-bar-fill" style={{ width: `${site.overall_pct}%`, background: STATUS_META[site.status].color }} />
      </div>
      <button className="btn-primary" style={{ width: '100%', marginTop: 14 }} onClick={() => onDetail(site)}>
        상세 보기
      </button>
    </div>
  )
}
