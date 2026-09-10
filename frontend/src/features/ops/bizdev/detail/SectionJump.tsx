// 상세 화면 목차 — 박스 이름을 눌러 그 박스로 건너뛴다.
// 박스가 늘어나 페이지가 길어졌고(인허가만 880px), 아래쪽 계통·조례까지
// 마우스로 굴려 내려가야 했다. 화면 위에 붙어 있어 어디서든 바로 옮겨 간다.
export interface JumpTarget {
  id: string
  label: string
}

export default function SectionJump({ targets }: { targets: JumpTarget[] }) {
  const go = (id: string) => {
    const el = document.getElementById(id)
    if (!el) return
    // 카드에 scroll-margin-top 을 주어 목차 띠에 가리지 않는다
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <nav className="bz-jump" aria-label="사업 상세 목차">
      {targets.map(t => (
        <button key={t.id} className="bz-jump-btn" onClick={() => go(t.id)}>
          {t.label}
        </button>
      ))}
    </nav>
  )
}
