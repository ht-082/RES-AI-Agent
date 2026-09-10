import { colStatus, ENERGY_META, PIPE_COLS, STATUS_META } from './constants'
import type { Site } from './types'

// 사업 List — 원본 index.page.js renderPipeline 이식.
// 7컬럼 상태 도출(colStatus) · 첫 미완료 컬럼 강조 · 행 클릭 → 상세.
// 진척도(%)는 상태에서 기계적으로 만든 수치라 의미가 없어 두지 않는다.
export default function PipelineTable({ sites, onSelectSite }: {
  sites: Site[]
  onSelectSite: (id: string) => void
}) {
  if (!sites.length) {
    return <p className="note" style={{ textAlign: 'center', padding: '28px 0' }}>등록된 사업지가 없습니다.</p>
  }
  const ordered = [...sites].sort((a, b) =>
    a.slug === 'hongseong-solar' ? -1 : b.slug === 'hongseong-solar' ? 1 : 0)

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="tbl" style={{ minWidth: 860 }}>
        <thead>
          <tr>
            <th style={{ width: 220 }}>사업지</th>
            {PIPE_COLS.map(c => (
              <th key={c.label} style={{ textAlign: 'center', whiteSpace: 'normal', lineHeight: 1.25, fontSize: 10.5 }}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ordered.map(site => {
            const cols = PIPE_COLS.map(c => colStatus(site.stages, c))
            const curIdx = cols.findIndex(s => s !== 'done')
            const e = ENERGY_META[site.energy_type]
            return (
              <tr key={site.id} className="bz-row" onClick={() => onSelectSite(site.id)}>
                <td>
                  <div style={{ fontSize: 12.5, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: e.color, flexShrink: 0 }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{site.name}</span>
                    {site.risk_tag && (
                      <span className="bz-chip" style={{
                        background: site.risk_level === 'hi' ? 'var(--red-soft)' : 'var(--amber-soft)',
                        color: site.risk_level === 'hi' ? 'var(--red)' : 'var(--amber)',
                      }}>{site.risk_tag}</span>
                    )}
                    {site.lifecycle === 'ops' && (
                      <span className="bz-chip" style={{ background: 'var(--mint-soft)', color: 'var(--green-600)' }}>운영</span>
                    )}
                  </div>
                  <div style={{ fontSize: 10.5, color: 'var(--ink-faint)', marginTop: 2 }}>
                    <span style={{ color: e.color, fontWeight: 600 }}>{e.label}</span> · {Math.round(Number(site.capacity_mw))}MW
                  </div>
                </td>
                {cols.map((s, i) => (
                  <td key={i} style={{ textAlign: 'center' }}
                      title={`${PIPE_COLS[i].label}: ${STATUS_META[s].label}`}>
                    <span className={`bz-dot ${i === curIdx ? 'cur' : ''}`}
                          style={{ background: STATUS_META[s].color }} />
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
