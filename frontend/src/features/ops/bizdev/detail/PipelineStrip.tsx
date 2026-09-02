import { colStatus, PIPE_COLS, STATUS_META } from '../constants'
import type { PermitStage } from '../types'

// 대시보드 사업 List 의 7단계 진척 표시를 상세에도 그린다.
// 같은 인허가 항목(stages)에서 같은 규칙(colStatus)으로 계산하므로,
// 상세에서 현황을 고치면 대시보드와 자동으로 같아진다 — 값을 따로 두지 않는다.
export default function PipelineStrip({ stages }: { stages: PermitStage[] }) {
  const cols = PIPE_COLS.map(c => colStatus(stages, c))
  const current = cols.findIndex(s => s !== 'done' && s !== 'na')

  const target = stages.filter(s => s.status !== 'na')
  const done = target.filter(s => s.status === 'done').length
  const pct = target.length ? Math.round((done / target.length) * 100) : 0

  return (
    <div className="bz-strip">
      <div className="bz-strip-head">
        <span className="bz-strip-title">진척 개요</span>
        <span className="bz-strip-note">
          대시보드 사업 List 와 같은 기준 · 완료 {done}/{target.length} ({pct}%)
        </span>
      </div>
      <div className="bz-strip-track">
        {PIPE_COLS.map((col, i) => (
          <div key={col.label} className="bz-strip-step">
            {i > 0 && <span className="bz-strip-line" />}
            <span className={`bz-dot ${i === current ? 'cur' : ''}`}
                  style={{ background: STATUS_META[cols[i]].color }}
                  title={`${col.label.replace(/\n/g, ' ')}: ${STATUS_META[cols[i]].label}`} />
            <span className="bz-strip-label">{col.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
