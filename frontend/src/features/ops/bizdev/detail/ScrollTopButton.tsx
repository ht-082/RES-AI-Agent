import { useEffect, useState } from 'react'
import { ArrowUp } from 'lucide-react'

// 맨 위로 — 목차 띠는 화면 위에 고정하지 않고 흘려보내므로, 아래로 내려간 뒤
// 목차로 돌아올 방법이 필요하다. 조금이라도 내려가면 나타난다.
const SHOW_AFTER = 260

export default function ScrollTopButton({ containerRef }: {
  containerRef: React.RefObject<HTMLElement | null>
}) {
  const [show, setShow] = useState(false)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const onScroll = () => setShow(el.scrollTop > SHOW_AFTER)
    onScroll()
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [containerRef])

  if (!show) return null

  return (
    <button className="bz-totop" title="맨 위로" aria-label="맨 위로"
            onClick={() => containerRef.current?.scrollTo({ top: 0, behavior: 'smooth' })}>
      <ArrowUp size={18} />
    </button>
  )
}
