import { useEffect, useState } from 'react'
import { apiGet } from './api'
import { sidoOf } from './constants'
import type { GridRegion, Site } from './types'

function satColor(pct: number): string {
  if (pct >= 50) return 'var(--red)'
  if (pct >= 25) return 'var(--amber)'
  return 'var(--green-accent)'
}

// 계통 접속 가능용량(시도별) — 원본 index.page.js renderGrid 이식.
// 사업지 설비용량을 시·도별 합산해 KEPCO 데이터가 있는 시·도 상위 8개만 표시.
export default function GridRail({ sites }: { sites: Site[] }) {
  const [regions, setRegions] = useState<GridRegion[]>([])
  useEffect(() => {
    let cancelled = false
    apiGet<GridRegion[]>('/api/bizdev/grid/capacity/')
      .then(d => { if (!cancelled) setRegions(d) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  const capMap = new Map(regions.map(r => [r.sido, r]))
  const byProv = new Map<string, number>()
  sites.forEach(s => {
    const p = sidoOf(s)
    if (!p) return
    byProv.set(p, (byProv.get(p) || 0) + Number(s.capacity_mw || 0))
  })
  const rows = [...byProv.entries()]
    .filter(([p]) => capMap.has(p))
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)

  return (
    <div className="card block" style={{ padding: 16 }}>
      <h3 style={{ fontSize: 13.5 }}>계통 접속 가능용량</h3>
      <div className="h-sub" style={{ marginBottom: 10 }}>시도별 · KEPCO 분산전원 연계정보</div>
      {rows.length === 0 && <p className="note">데이터 없음</p>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
        {rows.map(([prov, mw]) => {
          const cap = capMap.get(prov)!
          return (
            <div key={prov} style={{ fontSize: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                <span style={{ fontWeight: 600 }}>{prov} <span style={{ color: 'var(--ink-faint)', fontWeight: 400 }}>사업 {Math.round(mw)}MW</span></span>
                <span style={{ color: satColor(cap.sat_pct) }}>포화 {cap.sat_pct}% · 여유 {cap.available_mw.toLocaleString()}MW</span>
              </div>
              <div className="bz-bar">
                <div className="bz-bar-fill" style={{ width: `${Math.min(100, cap.sat_pct)}%`, background: satColor(cap.sat_pct) }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
