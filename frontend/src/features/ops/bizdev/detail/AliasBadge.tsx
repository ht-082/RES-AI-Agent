import type { SiteFact } from '../types'

// 제목 옆 "별칭 N개" 배지 — 마우스를 올리면 별칭 목록이 펼쳐진다.
export default function AliasBadge({ facts }: { facts?: SiteFact[] }) {
  const raw = facts?.find(f => f.section === 'basic' && f.key === 'aliases')?.value || ''
  const list = raw.split('\n').map(x => x.trim()).filter(Boolean)
  if (list.length === 0) return null

  return (
    <span className="bz-alias-badge">
      <span className="bz-chip" style={{ background: 'var(--surface-2)', color: 'var(--ink-soft)' }}>
        별칭 {list.length}개
      </span>
      <span className="bz-alias-pop">
        {list.map(a => <span key={a}>{a}</span>)}
      </span>
    </span>
  )
}
