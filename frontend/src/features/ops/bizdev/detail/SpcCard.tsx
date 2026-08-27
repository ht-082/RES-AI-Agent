import type { Site } from '../types'

// SPC 법인 정보 — 원본과 동일하게 클라이언트 더미 (DB화는 2차)
export default function SpcCard({ site }: { site: Site }) {
  const corp = `${(site.name || '').split(/[\s·(]/)[0] || '사업'} 발전 주식회사`
  const rows: Array<[string, string]> = [
    ['법인명', corp],
    ['대표이사', site.pm_name || '정혁태'],
    ['자본금', '30억원'],
    ['설립일', '2025.03.10'],
    ['본점 소재지', site.location || site.sido || '-'],
    ['사업자번호', '123-86-45678'],
  ]
  const holders = [
    ['재생E개발㈜', 60], ['인프라 사모펀드 I', 30], ['지역참여조합', 10],
  ] as const
  return (
    <div className="card block">
      <h3>SPC 법인 정보</h3>
      <div className="h-sub" style={{ marginBottom: 12 }}>예시 데이터 (법인 등록 연동 전)</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {rows.map(([k, v]) => (
          <div key={k}>
            <div style={{ fontSize: 10.5, color: 'var(--ink-faint)' }}>{k}</div>
            <div style={{ fontSize: 13, fontWeight: 600, marginTop: 2 }}>{v}</div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 14 }}>
        <div style={{ fontSize: 10.5, color: 'var(--ink-faint)', marginBottom: 6 }}>주주 구성</div>
        <div style={{ display: 'flex', height: 10, borderRadius: 6, overflow: 'hidden' }}>
          {holders.map(([name, pct], i) => (
            <div key={name} title={`${name} ${pct}%`} style={{
              width: `${pct}%`,
              background: ['var(--brand)', 'var(--green-accent)', 'var(--mint)'][i],
            }} />
          ))}
        </div>
        <div style={{ display: 'flex', gap: 14, marginTop: 6, fontSize: 11, color: 'var(--ink-soft)', flexWrap: 'wrap' }}>
          {holders.map(([name, pct]) => <span key={name}>{name} {pct}%</span>)}
        </div>
      </div>
    </div>
  )
}
