import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import type { SiteFact } from '../types'

// 지분구조를 도넛 + 범례로 그린다.
// 저장 형식은 "주주명 | 지분%" 줄 목록(텍스트)이라 md 내보내기에 영향이 없다.
const COLORS = ['var(--brand)', 'var(--green-accent)', 'var(--mint)',
                'var(--amber)', '#5b8cb8', '#8a6ea8']

export function parseShareholders(value: string) {
  return (value || '').split('\n').map(x => x.trim()).filter(Boolean).map(line => {
    const [name, pct] = line.split('|').map(s => s.trim())
    return { name: name || '(미상)', pct: parseFloat(pct) || 0 }
  })
}

export default function ShareholderBlock({ fact }: { fact: SiteFact }) {
  const rows = parseShareholders(fact.value)
  const total = rows.reduce((a, r) => a + r.pct, 0)

  if (rows.length === 0) {
    return (
      <div style={{ marginTop: 14 }}>
        <div className="bz-block-title">지분구조</div>
        <p className="note">등록된 주주가 없습니다.</p>
      </div>
    )
  }

  // 합이 100%가 아니면 도넛이 실제 비율을 왜곡하므로 남는 몫을 '미지정'으로 채운다
  const data = total < 100
    ? [...rows, { name: '미지정', pct: Math.round((100 - total) * 10) / 10 }]
    : rows

  return (
    <div style={{ marginTop: 14 }}>
      <div className="bz-block-title">
        지분구조
        {Math.abs(total - 100) > 0.01 && (
          <span className="bz-chip" style={{ background: 'var(--amber-soft)', color: 'var(--amber)' }}>
            합계 {total}%
          </span>
        )}
      </div>
      <div className="bz-share">
        <div style={{ width: 116, height: 116, flexShrink: 0 }}>
          <ResponsiveContainer>
            <PieChart>
              <Pie data={data} dataKey="pct" nameKey="name"
                   innerRadius={30} outerRadius={54} paddingAngle={1} stroke="none">
                {data.map((d, i) => (
                  <Cell key={d.name}
                        fill={d.name === '미지정' ? 'var(--line)' : COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v, n) => [`${v}%`, String(n)]} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="bz-share-legend">
          {data.map((d, i) => (
            <div key={d.name} className="bz-share-row">
              <span className="bz-share-dot" style={{
                background: d.name === '미지정' ? 'var(--line)' : COLORS[i % COLORS.length],
              }} />
              <span className="bz-share-name" title={d.name}>{d.name}</span>
              <span className="bz-share-pct">{d.pct}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
