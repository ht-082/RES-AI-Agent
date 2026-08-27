import { useEffect, useRef } from 'react'
import L from 'leaflet'
import { ENERGY_META, formatKRW } from '../constants'
import type { BudgetSummary, Site } from '../types'

// 사업 부지 개요 — 위성 미니 지도 + 8개 지표 (원본 project.html 카드1)
export default function OverviewCard({ site, budget }: { site: Site; budget?: BudgetSummary }) {
  const boxRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)

  useEffect(() => {
    if (!boxRef.current) return
    if (mapRef.current) { mapRef.current.remove(); mapRef.current = null }
    if (site.lat == null || site.lng == null) return
    const map = L.map(boxRef.current, { scrollWheelZoom: false, zoomControl: false })
      .setView([site.lat, site.lng], 13)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { attribution: 'Tiles &copy; Esri' }).addTo(map)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
      { attribution: '' }).addTo(map)
    const color = ENERGY_META[site.energy_type]?.color || '#f59e0b'
    L.marker([site.lat, site.lng], {
      icon: L.divIcon({
        className: 'bz-pin-wrap',
        html: `<div class="bz-pin" style="--pin-color:${color}"><span class="bz-pin-head"></span></div>`,
        iconSize: [26, 34], iconAnchor: [13, 30],
      }),
    }).addTo(map)
    mapRef.current = map
    return () => { map.remove(); mapRef.current = null }
  }, [site.id, site.lat, site.lng, site.energy_type])

  const rows: Array<[string, string]> = [
    ['소재 지역', site.location || site.sido || '-'],
    ['설비 유형', site.facility_type || '-'],
    ['에너지원', ENERGY_META[site.energy_type].label],
    ['설비용량', `${Math.round(Number(site.capacity_mw))} MW`],
    ['전체 진척도', `${site.overall_pct}%`],
    ['예산 집행률', budget ? `${budget.exec_pct}% (${formatKRW(budget.total)}/${formatKRW(budget.approved)})` : '-'],
    ['연간 발전량', site.annual_gwh ? `${site.annual_gwh} GWh` : '-'],
    ['목표 COD', site.cod || '-'],
  ]

  return (
    <div className="card block">
      <h3>사업 부지 개요</h3>
      <div className="h-sub" style={{ marginBottom: 12 }}>{site.name} · 담당 PM {site.pm_name || '-'}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: 14 }}>
        <div ref={boxRef} style={{ minHeight: 220, borderRadius: 10, overflow: 'hidden', background: 'var(--surface-2)' }}>
          {(site.lat == null || site.lng == null) && (
            <p className="note" style={{ padding: 20 }}>위경도 미입력 — 지도 표시 불가</p>
          )}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, alignContent: 'start' }}>
          {rows.map(([k, v]) => (
            <div key={k}>
              <div style={{ fontSize: 10.5, color: 'var(--ink-faint)' }}>{k}</div>
              <div style={{ fontSize: 13, fontWeight: 600, marginTop: 2 }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
