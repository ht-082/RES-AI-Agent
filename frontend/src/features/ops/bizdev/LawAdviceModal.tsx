import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { RefreshCw, Sparkles, X } from 'lucide-react'
import { apiSend } from './api'
import type { Law } from './types'

interface Advice {
  advice: string
  model: string
  created_at: string
  cached: boolean
}

// 법령 영향 제언 — 버튼을 누르면 정해진 질문에 이 법령 값만 끼워 물어본다.
// 한 번 만든 답은 서버가 캐시해 두므로 같은 법령을 다시 눌러도 곧바로 뜬다.
export default function LawAdviceModal({ law, onClose }: { law: Law; onClose: () => void }) {
  const [data, setData] = useState<Advice | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!loading) return
    setElapsed(0)
    const t = window.setInterval(() => setElapsed(v => v + 1), 1000)
    return () => window.clearInterval(t)
  }, [loading])

  const ask = async (refresh = false) => {
    setLoading(true)
    setError('')
    try {
      setData(await apiSend<Advice>('POST', `/api/bizdev/laws/${law.id}/advice/`, { refresh }))
    } catch (e) {
      setError(e instanceof Error ? e.message : '제언을 만들지 못했습니다.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void ask() }, [law.id])   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="bz-modal-back" onClick={onClose}>
      <div className="bz-modal bz-modal-wide" onClick={e => e.stopPropagation()}>
        <div className="bz-advice-head">
          <div>
            <h3 className="bz-advice-title"><Sparkles size={15} /> AI 제언 — {law.short_name || law.law_name}</h3>
            <p className="h-sub">
              {law.category} · {law.ministry}{law.date ? ` · ${law.date}` : ''}
              {data && !loading && (
                <> · {data.cached ? '저장된 제언' : '방금 생성'}
                  {data.model ? ` · ${data.model}` : ''}</>
              )}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn-ghost" disabled={loading} onClick={() => ask(true)}
                    title="다시 만들기">
              <RefreshCw size={14} />
            </button>
            <button className="btn-ghost" onClick={onClose} aria-label="닫기"><X size={16} /></button>
          </div>
        </div>

        <div className="bz-advice">
          {loading && (
            <div className="bz-advice-loading">
              <span className="bz-spinner" />
              <div>
                <p className="bz-advice-loading-title">제언을 만들고 있습니다</p>
                <p className="bz-advice-loading-sub">
                  보통 10~30초 걸립니다 · {elapsed}초 경과
                </p>
              </div>
            </div>
          )}
          {error && <p className="note" style={{ color: 'var(--red)' }}>{error}</p>}
          {!loading && !error && data && (
            <>
              <div className="bz-advice-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.advice}</ReactMarkdown>
              </div>
              <p className="bz-advice-foot">
                법령 메타데이터를 근거로 한 해석입니다. 시행 전 원문 확인이 필요합니다.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
