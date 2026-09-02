import type { SiteFact } from '../types'

// 지분구조도 — 주주 박스에서 선이 내려와 SPC 박스로 모이는 조직도 형태.
// 지분율은 박스가 아니라 연결선 옆에 붙인다.
// 배치: 주주가 3명 이하면 위→아래(세로 흐름), 4명 이상이면 왼쪽→오른쪽(가로 흐름).
//       이름이 길어 가로로 늘어놓으면 박스가 좁아지기 때문이다.
const VERTICAL_MAX = 3

export function parseShareholders(value: string) {
  const NL = String.fromCharCode(10)
  return (value || '').split(NL).map(x => x.trim()).filter(Boolean).map(line => {
    const [name, pct] = line.split('|').map(s => s.trim())
    return { name: name || '(미상)', pct: pct || '' }
  })
}

export default function ShareholderBlock({ fact, targetName }: {
  fact: SiteFact
  targetName?: string
}) {
  const rows = parseShareholders(fact.value)
  const total = rows.reduce((a, r) => a + (parseFloat(r.pct) || 0), 0)
  const target = targetName?.trim() || 'SPC'

  if (rows.length === 0) {
    return (
      <div style={{ marginTop: 14 }}>
        <div className="bz-block-title">지분구조</div>
        <p className="note">등록된 주주가 없습니다.</p>
      </div>
    )
  }

  const horizontal = rows.length > VERTICAL_MAX
  // 모이는 선은 첫 박스 중심에서 마지막 박스 중심까지만 그린다.
  // 박스 높이가 제각각이라 %로 계산할 수 없어, 주주 영역 안에 절대 배치하고
  // 양끝을 노드 절반만큼(=100%/2n) 안쪽으로 들여 정확히 중심에 맞춘다.
  const inset = `calc(100% / ${rows.length * 2})`
  const busStyle = horizontal
    ? { top: inset, bottom: inset, right: 0 }
    : { left: inset, right: inset, bottom: 0 }

  return (
    <div style={{ marginTop: 14 }}>
      <div className="bz-block-title">
        지분구조
        {Math.abs(total - 100) > 0.01 && rows.some(r => r.pct) && (
          <span className="bz-chip" style={{ background: 'var(--amber-soft)', color: 'var(--amber)' }}>
            합계 {total}%
          </span>
        )}
      </div>

      <div className={`bz-org ${horizontal ? 'h' : 'v'}`}>
        <div className="bz-org-holders">
          {rows.map((r, i) => (
            <div key={`${r.name}-${i}`} className="bz-org-node">
              <div className="bz-org-box" title={r.name}>{r.name}</div>
              <div className="bz-org-stub">
                {r.pct && <span className="bz-org-pct">{r.pct}%</span>}
              </div>
            </div>
          ))}
          {rows.length > 1 && <div className="bz-org-bus" style={busStyle} />}
        </div>

        <div className="bz-org-drop" />

        <div className="bz-org-box bz-org-target" title={target}>{target}</div>
      </div>
    </div>
  )
}
