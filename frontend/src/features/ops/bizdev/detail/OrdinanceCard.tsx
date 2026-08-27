import { useEffect, useState } from 'react'
import { ExternalLink } from 'lucide-react'
import { apiGet } from '../api'
import type { Law } from '../types'

// 지자체 조례 모니터링 — 원본 project.html 카드6 (법제처 스냅샷 기반, 실시간은 2차)
export default function OrdinanceCard({ sido }: { sido: string }) {
  const [rows, setRows] = useState<Law[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    apiGet<Law[]>(`/api/bizdev/ordinances/?sido=${encodeURIComponent(sido || '')}`)
      .then(d => { if (!cancelled) setRows(d.slice(0, 8)) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoaded(true) })
    return () => { cancelled = true }
  }, [sido])

  return (
    <div className="card block">
      <h3>지자체 조례 모니터링</h3>
      <div className="h-sub" style={{ marginBottom: 12 }}>재생에너지 관련 조례 (법제처 국가법령정보)</div>
      {loaded && rows.length === 0 && <p className="note">관련 조례가 없습니다.</p>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
        {rows.map(l => (
          <a key={l.id} href={l.source_url || undefined} target="_blank" rel="noreferrer"
             style={{ display: 'block', textDecoration: 'none', color: 'inherit' }}>
            <div style={{ fontSize: 12.5, fontWeight: 500, lineHeight: 1.4 }}>
              {l.law_name} <ExternalLink size={10} style={{ display: 'inline', verticalAlign: '-1px', color: 'var(--ink-faint)' }} />
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--ink-faint)', marginTop: 2 }}>
              {l.ministry}{l.date ? ` · 시행 ${l.date}` : ''}{l.category ? ` · ${l.category}` : ''}
            </div>
          </a>
        ))}
      </div>
    </div>
  )
}
