import { useEffect, useState } from 'react'
import { apiGet } from '../api'
import type { GridSubstation } from '../types'

const STATUS_COLOR: Record<string, string> = {
  포화: 'var(--red)', 주의: 'var(--amber)', 여유: 'var(--green-accent)',
}

// 계통 상황 — 인근 변전소 8개 (원본 project.html 카드5, KEPCO 스냅샷 기반)
export default function GridCard({ sido }: { sido: string }) {
  const [subs, setSubs] = useState<GridSubstation[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    apiGet<GridSubstation[]>(`/api/bizdev/grid/nearby/?sido=${encodeURIComponent(sido || '')}`)
      .then(d => { if (!cancelled) setSubs(d) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoaded(true) })
    return () => { cancelled = true }
  }, [sido])

  return (
    <div className="card block">
      <h3>계통 상황</h3>
      <div className="h-sub" style={{ marginBottom: 12 }}>
        인근 변전소 접속 여유 (KEPCO 분산전원 연계정보 · 여유 적은 순)
      </div>
      {loaded && subs.length === 0 && <p className="note">계통 데이터가 없습니다.</p>}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10 }}>
        {subs.map(s => (
          <div key={s.name} style={{
            border: '1px solid var(--line)', borderRadius: 10, padding: '10px 12px',
            background: 'var(--surface-2)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 12.5, fontWeight: 700 }}>{s.name}</span>
              <span className="bz-chip" style={{
                background: `color-mix(in srgb, ${STATUS_COLOR[s.contract_status]} 14%, transparent)`,
                color: STATUS_COLOR[s.contract_status],
              }}>{s.contract_status}</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--ink-soft)', marginTop: 4 }}>
              {s.sido} · 사용률 {s.capacity_used_pct}%
            </div>
            <div style={{ fontSize: 12, fontWeight: 600, marginTop: 2 }}>
              여유 {s.available_mw.toLocaleString()} MW
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
