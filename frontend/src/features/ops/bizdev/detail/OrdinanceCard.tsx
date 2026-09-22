import { useEffect, useState } from 'react'
import { ExternalLink, Sparkles } from 'lucide-react'
import SectionHead from './SectionHead'
import { apiGet } from '../api'
import { useAdvice } from '../advice'
import type { Law } from '../types'

// 지자체 조례 모니터링 — 원본 project.html 카드6 (법제처 스냅샷 기반, 실시간은 2차)
//
// 그 시·군 조례와 도 차원 조례를 갈라서 보여 준다. 예전에는 같은 도라는
// 이유로 다른 시·군 조례까지 올라와(당진 사업 화면에 보령시 조례) 검토해야
// 할 규정으로 읽혔다. 또 시·군 조례가 자료에 없을 때 그냥 비워 두면 '조례가
// 없다' 로 읽히므로, 확인되지 않았다고 분명히 적는다.
//
// 'AI 제언'은 법령 동향과 같은 흐름이되, 질문에 이 사업의 지역·용량·인허가
// 단계가 들어간다 — 조례는 전국이 아니라 이 사업지에서만 걸리기 때문이다.
export default function OrdinanceCard({ sido, siteId, onOpenChat, id }: {
  sido: string
  siteId: string
  onOpenChat?: (conversationId: string) => void
  id?: string
}) {
  const [rows, setRows] = useState<Law[]>([])
  const [loaded, setLoaded] = useState(false)
  const advice = useAdvice(onOpenChat)

  useEffect(() => {
    let cancelled = false
    setLoaded(false)
    apiGet<Law[]>(`/api/bizdev/ordinances/?sido=${encodeURIComponent(sido || '')}`)
      .then(d => { if (!cancelled) setRows(d.slice(0, 8)) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoaded(true) })
    return () => { cancelled = true }
  }, [sido])

  const local = rows.filter(r => r.scope === 'local')
  const province = rows.filter(r => r.scope !== 'local')

  const item = (l: Law) => (
    <div key={l.id} className="bz-ord-row">
      <a className="bz-ord-name" href={l.source_url || undefined}
         target="_blank" rel="noreferrer">
        {l.law_name} <ExternalLink size={10} />
      </a>
      <div className="bz-ord-foot">
        <span className="bz-ord-meta">
          {l.ministry}{l.date ? ` · 시행 ${l.date}` : ''}{l.category ? ` · ${l.category}` : ''}
        </span>
        {advice.canAsk && (
          <button className="btn-ghost bz-law-ai" disabled={advice.busyId === l.id}
                  onClick={() => advice.ask(l.id, l.law_name,
                    `/api/bizdev/ordinances/${l.id}/advice-prompt/?site=${siteId}`)}
                  title="이 조례가 이 사업에 미칠 영향을 챗봇에 물어봅니다">
            <Sparkles size={12} /> {advice.busyId === l.id ? '여는 중' : '제언'}
          </button>
        )}
      </div>
    </div>
  )

  return (
    <div className="card block" id={id}>
      <SectionHead title="지자체 조례 모니터링" />
      <div className="h-sub" style={{ marginBottom: 12 }}>
        {sido ? `${sido} 및 상위 시·도 조례` : '재생에너지 관련 조례'} (법제처 국가법령정보)
      </div>
      <div className="bz-scroll bz-scroll-rail">
        {loaded && (
          <>
            <div className="bz-ord-group">{sido || '해당 지자체'} 조례</div>
            {local.length === 0 ? (
              <p className="note bz-ord-none">
                확보된 자료에 없습니다 — 조례가 없다는 뜻은 아닙니다.
                법제처 실시간 연동 시 채워집니다.
              </p>
            ) : local.map(item)}

            <div className="bz-ord-group">상위 시·도 조례</div>
            {province.length === 0 ? (
              <p className="note bz-ord-none">확보된 자료에 없습니다.</p>
            ) : province.map(item)}
          </>
        )}
      </div>
      {advice.toast}
    </div>
  )
}
