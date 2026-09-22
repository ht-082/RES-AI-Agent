import { useEffect, useState } from 'react'
import { apiGet, apiSend } from './api'

// 'AI 제언' 공통 동작 — 정해진 질문을 사내 챗봇에 넣고 그 화면으로 넘긴다.
// 검색·출처·이어 묻기는 챗봇이 하던 대로 한다(우리가 그 파이프라인을 복제하지
// 않는다). 법령 동향과 조례 모니터링이 같은 흐름을 쓰므로 여기 모아 둔다.
//
// 답을 받은 뒤에 화면을 옮긴다 — 먼저 옮기면 챗봇이 아직 비어 있는 대화를 읽고
// 끝나 버린다(같은 대화 id 라 다시 읽지도 않는다). 그래서 30초~1분을 기다리게
// 되고, 멈춘 것처럼 보이지 않게 경과 시간을 띄운다.
// 건마다 새 대화를 연다 — 사람마다 후속 질문을 따로 이어갈 수 있도록.
export function useAdvice(onOpenChat?: (conversationId: string) => void) {
  const [busyId, setBusyId] = useState<string | null>(null)
  const [label, setLabel] = useState('')
  const [sec, setSec] = useState(0)

  useEffect(() => {
    if (!busyId) return
    setSec(0)
    const t = window.setInterval(() => setSec(v => v + 1), 1000)
    return () => window.clearInterval(t)
  }, [busyId])

  const ask = async (id: string, name: string, promptUrl: string) => {
    if (!onOpenChat) return
    setBusyId(id)
    setLabel(name)
    try {
      const { title, prompt } = await apiGet<{ title: string; prompt: string }>(promptUrl)
      const conv = await apiSend<{ id: string }>('POST', '/api/conversations/',
                                                 { title, use_internal_docs: true })
      await apiSend('POST', `/api/conversations/${conv.id}/messages/`, { content: prompt })
      onOpenChat(conv.id)
    } catch (e) {
      alert(e instanceof Error ? e.message : '챗봇으로 넘기지 못했습니다.')
    } finally {
      setBusyId(null)
    }
  }

  const toast = busyId ? (
    <div className="bz-advice-toast">
      <span className="bz-spinner" />
      <div>
        <p className="bz-advice-loading-title">AI 제언을 만들고 있습니다</p>
        <p className="bz-advice-loading-sub">
          {label} · 사내 자료를 찾아 답을 씁니다 · {sec}초 경과
        </p>
        <p className="bz-advice-loading-sub">다 되면 대화 화면으로 넘어갑니다 (보통 30초~1분)</p>
      </div>
    </div>
  ) : null

  return { busyId, ask, toast, canAsk: !!onOpenChat }
}
