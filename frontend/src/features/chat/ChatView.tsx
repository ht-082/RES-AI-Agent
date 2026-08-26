import { useState, useRef, useEffect, type ReactNode } from 'react'
import { Send, Paperclip, FileText, Copy, Check, Printer } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import MermaidBlock from './MermaidBlock'
import TableChart from './TableChart'
import VizBlock from './VizBlock'

/** Markdown 요소 → 컴포넌트 매핑.
 *
 *  **반드시 모듈 상수여야 한다.** 컴포넌트 안에서 객체 리터럴로 만들면 렌더마다
 *  함수 정체성이 바뀌고, react-markdown이 이를 다른 컴포넌트로 보아 하위 트리를
 *  통째로 언마운트·재마운트한다. 입력창에 글자를 칠 때마다(setInput → 리렌더)
 *  이미 그려진 도식이 다시 그려지면서 화면이 흔들렸다.
 */
const MD_COMPONENTS = {
  // 표는 가로 스크롤로 감싸고, 숫자 열이 있으면 차트 전환 버튼을 붙인다.
  // 차트는 이 표의 DOM을 그대로 읽어 그리므로 수치가 어긋날 수 없다.
  table: ({ children }: { children?: ReactNode }) => (
    <TableChart>
      <div className="md-table-wrap"><table>{children}</table></div>
    </TableChart>
  ),
  // ```mermaid 는 도식, ```viz:<유형> 은 전용 컴포넌트로 보낸다.
  // 정규식이 \w+ 였을 때는 'viz:timeline'에서 ':' 앞까지만 잡혀 유형을 잃었다.
  code: ({ className, children, ...props }: { className?: string; children?: ReactNode }) => {
    const lang = /language-([\w:.-]+)/.exec(className ?? '')?.[1]
    if (lang === 'mermaid') {
      return <MermaidBlock code={String(children)} />
    }
    if (lang?.startsWith('viz:')) {
      // code 자리에 렌더되므로 `.md code`의 모노스페이스·배경 규칙을 그대로
      // 물려받는다. viz는 코드가 아니라 UI라서 래퍼로 그 규칙을 끊는다.
      return (
        <span className="viz-host">
          <VizBlock type={lang.slice(4)} source={String(children)} />
        </span>
      )
    }
    return <code className={className} {...props}>{children}</code>
  },
  // 출처 링크는 새 탭으로
  a: ({ href, children }: { href?: string; children?: ReactNode }) => (
    <a href={href} target="_blank" rel="noreferrer">{children}</a>
  ),
}

/** GET/POST /api/conversations/{id}/messages 의 sources 배열 항목
 *  (backend: apps/chat/serializers.py MessageSourceSerializer) */
interface Source {
  id?: string
  document_id?: string
  short_label: string
  display_title: string
  page_number: number | null
  location_label: string
  open_url: string | null
  score: number
  rank?: number
  snippet?: string
  /** 'internal' = 사내 문서 · 'web' = 웹 검색. 없으면 사내(기존 데이터 호환) */
  kind?: 'internal' | 'web'
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  used_internal_docs?: boolean
  sources?: Source[]
}

/** GET/POST /api/conversations/{id}/attachments 응답 (C-6) */
interface Attachment {
  id: string
  filename: string
  file_type: string
  file_size: number | null
  /** 업로드 응답에만 담긴다. false면 텍스트 추출에 실패한 것 */
  parsed?: boolean
}

const ATTACH_ACCEPT = '.pdf,.docx,.xlsx,.pptx,.hwp,.hwpx'

/** GET /api/corpus-versions/ 응답 항목 — 코퍼스 버전 선택용 */
/** GET /api/llm-models/ 응답 항목 */
interface LlmModel {
  id: string
  label: string
  note: string
  tier: string
}

interface CorpusVersion {
  version: string
  major: number
  is_active: boolean
  description: string
  doc_count: number
}

/** 출처 칩이 열 원문 URL.
 *  브라우저 PDF 뷰어는 #page=N 프래그먼트로 해당 페이지를 바로 연다.
 *  (Word/Excel 등은 프래그먼트를 못 쓰므로 파일만 열린다.) */
function sourceHref(src: Source): string {
  if (!src.open_url) return '#'
  return src.page_number ? `${src.open_url}#page=${src.page_number}` : src.open_url
}

interface ChatViewProps {
  /** 선택된 대화. null이면 아직 만들어지지 않은 새 대화 */
  conversationId: string | null
  /** 새 대화가 만들어졌거나 목록 갱신이 필요할 때 호출 */
  onConversationChanged: (id: string) => void
}

export default function ChatView({ conversationId, onConversationChanged }: ChatViewProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [useInternalDocs, setUseInternalDocs] = useState(true)
  // 웹 검색은 기본 꺼짐 — 켜면 질문 내용이 외부 검색 서비스로 전송된다
  const [useWebSearch, setUseWebSearch] = useState(false)
  const [sending, setSending] = useState(false)
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [uploading, setUploading] = useState(false)
  const [attachError, setAttachError] = useState<string | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  // 답변 대기 중 경과 시간(초)과 서버가 알려주는 현재 단계(SSE status 이벤트)
  const [elapsed, setElapsed] = useState(0)
  const [stage, setStage] = useState('')
  // 코퍼스 버전 선택 ('' = 활성 기본 버전)
  const [corpusVersions, setCorpusVersions] = useState<CorpusVersion[]>([])
  const [corpusVersion, setCorpusVersion] = useState('')
  // 답변 생성 모델. 빈 값 = 서버 기본값 사용
  const [llmModels, setLlmModels] = useState<LlmModel[]>([])
  const [llmDefault, setLlmDefault] = useState('')
  const [llmModel, setLlmModel] = useState('')

  useEffect(() => {
    fetch('/api/corpus-versions/', { credentials: 'include' })
      .then(res => (res.ok ? res.json() : []))
      .then(data => setCorpusVersions(Array.isArray(data) ? data : []))
      .catch(() => setCorpusVersions([]))

    fetch('/api/llm-models/', { credentials: 'include' })
      .then(res => (res.ok ? res.json() : null))
      .then(data => {
        if (!data) return
        setLlmModels(Array.isArray(data.models) ? data.models : [])
        setLlmDefault(data.default ?? '')
      })
      .catch(() => setLlmModels([]))
  }, [])

  const handleModelChange = async (v: string) => {
    setLlmModel(v)
    // 이미 만들어진 대화면 서버에도 반영 (다음 질의부터 해당 모델 사용)
    if (liveConvId.current) {
      try {
        const csrf = await getCsrf()
        await fetch(`/api/conversations/${liveConvId.current}/`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          body: JSON.stringify({ llm_model: v }),
          credentials: 'include',
        })
      } catch {
        /* 실패해도 이번 질의에는 아래 body 의 llm_model 이 쓰인다 */
      }
    }
  }

  const handleCorpusChange = async (v: string) => {
    setCorpusVersion(v)
    // 이미 만들어진 대화면 서버에도 반영 (다음 질의부터 해당 코퍼스로 검색)
    if (liveConvId.current) {
      try {
        const csrf = await getCsrf()
        await fetch(`/api/conversations/${liveConvId.current}/`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          body: JSON.stringify({ corpus_version: v }),
          credentials: 'include',
        })
      } catch { /* 실패 시 다음 전송에서 재시도됨 */ }
    }
  }
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // props는 비동기로 갱신되므로, 첨부 직후 곧바로 전송하는 경우를 대비해
  // 현재 대화 id를 ref로도 들고 있는다.
  const liveConvId = useRef<string | null>(conversationId)
  useEffect(() => { liveConvId.current = conversationId }, [conversationId])

  // 전송 중 새 대화가 만들어지면 conversationId가 바뀌면서 메시지 로딩 효과가 돌아
  // 화면에 쌓고 있던 질문·스트리밍 답변을 서버 응답(아직 비어 있음)으로 덮어쓴다.
  // 우리가 방금 만든 대화는 로딩을 건너뛴다.
  const skipLoadFor = useRef<string | null>(null)

  const getCsrf = async (): Promise<string> => {
    const res = await fetch('/api/auth/csrf/', { credentials: 'include' })
    const data = await res.json()
    return data.csrfToken
  }

  /** 대화가 없으면 만들고 id를 돌려준다. (첨부/전송이 공통으로 쓴다) */
  const ensureConversation = async (): Promise<string> => {
    if (liveConvId.current) return liveConvId.current
    const csrf = await getCsrf()
    const res = await fetch('/api/conversations/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify({ title: '', use_internal_docs: useInternalDocs, use_web_search: useWebSearch, llm_model: llmModel, corpus_version: corpusVersion }),
      credentials: 'include',
    })
    if (!res.ok) throw new Error('대화 생성 실패')
    const data = await res.json()
    liveConvId.current = data.id
    skipLoadFor.current = data.id   // 방금 만든 대화 — 서버에서 다시 읽어오지 않는다
    onConversationChanged(data.id)
    return data.id
  }

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, sending])

  // 답변 대기 중에만 경과 시간을 센다.
  useEffect(() => {
    if (!sending) {
      setElapsed(0)
      return
    }
    const startedAt = Date.now()
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000))
    }, 500)
    return () => clearInterval(timer)
  }, [sending])

  // 선택된 대화의 첨부 목록을 불러온다.
  useEffect(() => {
    setAttachError(null)
    if (!conversationId) {
      setAttachments([])
      return
    }
    let cancelled = false
    fetch(`/api/conversations/${conversationId}/attachments/`, { credentials: 'include' })
      .then(res => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then(data => { if (!cancelled) setAttachments(Array.isArray(data) ? data : []) })
      .catch(() => { if (!cancelled) setAttachments([]) })
    return () => { cancelled = true }
  }, [conversationId])

  // 선택된 대화의 지난 메시지를 불러온다. (새 대화면 비운다)
  useEffect(() => {
    if (!conversationId) {
      setMessages([])
      return
    }
    // 전송 중 우리가 만든 대화라면 화면에 쌓고 있는 내용을 유지한다
    if (skipLoadFor.current === conversationId) {
      skipLoadFor.current = null
      return
    }
    let cancelled = false
    fetch(`/api/conversations/${conversationId}/`, { credentials: 'include' })
      .then(res => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then(data => {
        if (cancelled) return
        const loaded: Message[] = (data.messages ?? [])
          .filter((m: any) => m.role === 'user' || m.role === 'assistant')
          .map((m: any) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            used_internal_docs: m.used_internal_docs,
            sources: m.sources ?? [],
          }))
        setMessages(loaded)
        if (typeof data.use_web_search === 'boolean') {
          setUseWebSearch(data.use_web_search)
        }
        if (typeof data.use_internal_docs === 'boolean') {
          setUseInternalDocs(data.use_internal_docs)
        }
        setCorpusVersion(data.corpus_version ?? '')
        setLlmModel(data.llm_model ?? '')
      })
      .catch(() => { if (!cancelled) setMessages([]) })
    return () => { cancelled = true }
  }, [conversationId])

  /** 답변을 Markdown 원문 + 출처 목록으로 복사 (엑셀·워드에 표 그대로 붙습니다) */
  const handleCopy = async (msg: Message) => {
    const srcLines = (msg.sources || []).map(
      (s, i) => `${i + 1}. ${s.display_title}${s.location_label ? ` (${s.location_label})` : ''}`
    )
    const text = srcLines.length
      ? `${msg.content}\n\n---\n참조한 사내 자료 ${srcLines.length}건\n${srcLines.join('\n')}`
      : msg.content
    try {
      await navigator.clipboard.writeText(text)
      setCopiedId(msg.id)
      setTimeout(() => setCopiedId(null), 1800)
    } catch {
      alert('복사에 실패했습니다. 브라우저 권한을 확인해 주세요.')
    }
  }

  /** 이 답변만 새 창으로 열어 인쇄 → 브라우저의 "PDF로 저장" 사용 */
  const handlePrint = (msg: Message) => {
    const node = document.getElementById(`msg-${msg.id}`)
    if (!node) return
    const w = window.open('', '_blank', 'width=900,height=1000')
    if (!w) { alert('팝업이 차단되었습니다. 팝업 허용 후 다시 시도해 주세요.'); return }
    // 화면 스타일을 그대로 가져와 인쇄본 모양을 맞춘다
    const styles = [...document.querySelectorAll('style, link[rel="stylesheet"]')]
      .map(el => el.outerHTML).join('')
    const stamp = new Date().toLocaleString('ko-KR')
    w.document.write(`<!doctype html><html lang="ko"><head><meta charset="utf-8">
      <title>재생E AI Agent 답변</title>${styles}
      <style>
        body { background:#fff; padding:28px 32px; }
        .print-head { border-bottom:1px solid #E4EAE5; padding-bottom:10px; margin-bottom:18px; }
        .print-head b { font-size:15px; color:#153F35; }
        .print-head span { float:right; font-size:11.5px; color:#8A988F; }
        .no-print { display:none !important; }
        .chip .tip { display:none !important; }
        table { page-break-inside:avoid; }
      </style></head><body>
      <div class="print-head"><b>재생E AI Agent</b><span>${stamp}</span></div>
      ${node.innerHTML}
      </body></html>`)
    w.document.close()
    // 스타일 로드 후 인쇄 대화상자를 띄운다
    w.onload = () => { w.focus(); w.print() }
  }

  const handleAttachClick = () => fileInputRef.current?.click()

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''  // 같은 파일 재선택도 동작하도록 초기화
    if (!file) return

    setUploading(true)
    setAttachError(null)
    try {
      const convId = await ensureConversation()
      const csrf = await getCsrf()
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`/api/conversations/${convId}/attachments/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf },   // FormData는 Content-Type을 브라우저가 정한다
        body: form,
        credentials: 'include',
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.error || '업로드 실패')

      setAttachments(prev => [...prev, data])
      if (data.parsed === false) {
        setAttachError(`${file.name}: 텍스트를 추출하지 못해 답변에 반영되지 않습니다.`)
      }
    } catch (err: any) {
      setAttachError(err?.message || '파일 첨부에 실패했습니다.')
    } finally {
      setUploading(false)
    }
  }

  const handleSend = async () => {
    if (!input.trim() || sending) return

    const currentInput = input.trim()
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: currentInput,
    }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setSending(true)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }

    // 답변이 흘러 들어올 자리를 미리 만든다 (스트리밍으로 여기에 이어붙인다)
    const draftId = `draft-${Date.now()}`
    setMessages(prev => [...prev, { id: draftId, role: 'assistant', content: '', sources: [] }])

    const patchDraft = (fn: (m: Message) => Message) =>
      setMessages(prev => prev.map(m => (m.id === draftId ? fn(m) : m)))

    try {
      // 1. 방이 없으면 만든다 (첨부로 이미 만들어졌을 수도 있다)
      const convId = await ensureConversation()

      // 2. SSE 스트리밍 요청 — 검색 단계와 본문 조각이 실시간으로 도착한다
      const csrf = await getCsrf()
      const res = await fetch(`/api/conversations/${convId}/messages/stream/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ content: currentInput, use_internal_docs: useInternalDocs, use_web_search: useWebSearch, llm_model: llmModel }),
        credentials: 'include',
      })
      if (!res.ok || !res.body) throw new Error('검색 또는 생성 실패')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      // SSE 프레임은 빈 줄로 구분된다. 조각이 잘려 도착할 수 있어 버퍼에 모아 파싱한다.
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        let sep: number
        while ((sep = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, sep)
          buffer = buffer.slice(sep + 2)

          const evLine = frame.split('\n').find(l => l.startsWith('event: '))
          const dataLine = frame.split('\n').find(l => l.startsWith('data: '))
          if (!evLine || !dataLine) continue
          const event = evLine.slice(7).trim()
          let payload: any = {}
          try { payload = JSON.parse(dataLine.slice(6)) } catch { continue }

          if (event === 'status') {
            setStage(payload.message || '')
          } else if (event === 'sources') {
            // 출처는 답변보다 먼저 확정되므로 근거를 즉시 보여준다
            patchDraft(m => ({ ...m, sources: payload.sources || [], used_internal_docs: true }))
          } else if (event === 'delta') {
            patchDraft(m => ({ ...m, content: m.content + (payload.text || '') }))
          } else if (event === 'done') {
            patchDraft(m => ({
              ...m,
              id: payload.message_id || m.id,
              used_internal_docs: payload.used_internal_docs ?? m.used_internal_docs,
            }))
          } else if (event === 'error') {
            patchDraft(m => ({ ...m, content: `⚠️ ${payload.message || '오류가 발생했습니다.'}` }))
          }
        }
      }

      // 3. 사이드바 갱신 (첫 질문으로 제목이 확정되므로 목록을 다시 읽는다)
      onConversationChanged(convId)

    } catch (err) {
      console.error(err)
      patchDraft(m => ({
        ...m,
        content: m.content || '⚠️ 서버(LLM 또는 검색 엔진)와 통신 중 오류가 발생했습니다.',
      }))
    } finally {
      setSending(false)
      setStage('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const ta = e.target
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
  }

  /** 답변 본문 렌더링 — 컴포넌트 매핑은 모듈 상수(MD_COMPONENTS)를 쓴다. 이유는 그 정의부 참고. */
  const renderContent = (content: string) => (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
      {content}
    </ReactMarkdown>
  )

  return (
    <section className="chat-wrap" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div className="chat-scroll" ref={scrollRef}>
        <div className="chat-inner">
          {messages.length === 0 && (
            <div className="chat-empty">
              <div className="ce-mark">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2a7 7 0 0 0-7 7c0 3 2 5 4 7l3 6 3-6c2-2 4-4 4-7a7 7 0 0 0-7-7Z" />
                </svg>
              </div>
              <h2>무엇을 도와드릴까요?</h2>
              <p>사업개발실 자료를 근거로 답변하고, 참조한 원문을 함께 보여드립니다.</p>
              {/* 검색은 질문 문장 그대로 수행된다. 사업명이 없으면 어느 사업 자료인지
                  가려낼 단서가 없어 다른 사업이 섞이거나 답을 찾지 못한다.
                  특히 "그건 얼마야?"처럼 앞 대화를 이어받는 질문이 취약하다. */}
              <p className="ce-note">
                질문에는 <strong>사업명을 반드시 포함</strong>해 주세요.
                이어서 묻더라도 매번 적어야 정확히 찾습니다.
              </p>
            </div>
          )}
          {/* 본문이 아직 비어 있는 초안(스트리밍 시작 전)은 대기 표시가 대신하므로 건너뛴다 */}
          {messages.filter(m => m.content || m.role === 'user').map(msg => (
            <div key={msg.id} id={`msg-${msg.id}`} className={`msg ${msg.role === 'user' ? 'user' : 'ai'}`}>
              <div className="ava">
                {msg.role === 'user' ? '관' : (
                  <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2a7 7 0 0 0-7 7c0 3 2 5 4 7l3 6 3-6c2-2 4-4 4-7a7 7 0 0 0-7-7Z"/>
                  </svg>
                )}
              </div>
              <div className="body">
                <div className="who">
                  {msg.role === 'user' ? '관리자' : '재생E AI Agent'}
                  {msg.used_internal_docs && <span className="ref-tag">사내 문서 참조</span>}
                </div>
                <div className="text md">
                  {renderContent(msg.content)}
                </div>
                {msg.role === 'assistant' && msg.content && (
                  <div className="msg-actions no-print">
                    <button onClick={() => handleCopy(msg)} title="Markdown으로 복사">
                      {copiedId === msg.id ? <Check size={13} /> : <Copy size={13} />}
                      {copiedId === msg.id ? '복사됨' : '복사'}
                    </button>
                    <button onClick={() => handlePrint(msg)} title="인쇄 · PDF로 저장">
                      <Printer size={13} />
                      PDF 저장
                    </button>
                  </div>
                )}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="sources">
                    <div className="s-lab">
                      <FileText size={13} />
                      참조한 사내 자료 {msg.sources.length}건
                    </div>
                    <div className="chips">
                      {msg.sources.map((src, i) => {
                        const body = (
                          <>
                            <span className="dot" />
                            {src.kind === 'web' && <span className="chip-tag">웹</span>}
                            {src.short_label}
                            <span className="tip">
                              {src.display_title}
                              {src.location_label && (
                                <span className="tp-meta">{src.location_label}</span>
                              )}
                              {src.kind === 'web' && (
                                <span className="tp-meta">웹 검색 결과 · 출처 신뢰도는 확인되지 않았습니다</span>
                              )}
                            </span>
                          </>
                        )
                        // 원문을 열 수 없는 출처(문서 삭제 등)는 링크로 만들지 않는다.
                        const cls = `chip${src.open_url ? ' is-link' : ''}${src.kind === 'web' ? ' is-web' : ''}`
                        return src.open_url ? (
                          <a
                            key={src.id ?? i}
                            className={cls}
                            href={sourceHref(src)}
                            target="_blank"
                            rel="noreferrer"
                            title={src.kind === 'web' ? '웹 원문 열기' : '원문 열기'}
                          >
                            {body}
                          </a>
                        ) : (
                          <span key={src.id ?? i} className={cls}>{body}</span>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* 답변 대기 표시. 서버가 알려주는 단계 + 실제 경과 시간.
              본문이 흘러들어오기 시작하면(스트리밍) 감춘다. */}
          {sending && !messages[messages.length - 1]?.content && (
            <div className="msg ai" aria-live="polite">
              <div className="ava">
                <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2a7 7 0 0 0-7 7c0 3 2 5 4 7l3 6 3-6c2-2 4-4 4-7a7 7 0 0 0-7-7Z"/>
                </svg>
              </div>
              <div className="body">
                <div className="who">재생E AI Agent</div>
                <div className="thinking">
                  <span className="dots" aria-hidden="true"><i /><i /><i /></span>
                  <span className="tk-txt">
                    {stage || (useInternalDocs ? '사내 자료를 검색하고 있습니다' : '답변을 준비하고 있습니다')}
                  </span>
                  <span className="tk-time">{elapsed}초</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Composer */}
      <div className="composer">
        <div className="composer-inner">
          <div className="ref-toggle">
            <label className="switch">
              <input
                type="checkbox"
                checked={useInternalDocs}
                onChange={e => setUseInternalDocs(e.target.checked)}
              />
              <span className="track" />
              <span className="knob" />
            </label>
            <div>
              <span className="rt-txt">사내 문서 참조</span>
              <span className="rt-sub"> · 이 대화에서 부서 자료를 검색해 답변에 반영합니다</span>
            </div>

            <label className="switch web-switch" title="켜면 질문 내용이 외부 검색 서비스로 전송됩니다">
              <input
                type="checkbox"
                checked={useWebSearch}
                onChange={e => setUseWebSearch(e.target.checked)}
              />
              <span className="track" />
              <span className="knob" />
            </label>
            <div>
              <span className="rt-txt">웹 검색</span>
              <span className="rt-sub">
                {useWebSearch
                  ? ' · ⚠ 질문 내용이 외부로 전송됩니다'
                  : ' · 법령·시세 등 사내 자료에 없는 정보를 보완합니다'}
              </span>
            </div>
            {llmModels.length > 0 && (
              <select
                className="corpus-select model-select"
                value={llmModel}
                onChange={e => handleModelChange(e.target.value)}
                title={
                  llmModels.find(m => m.id === (llmModel || llmDefault))?.note
                  ?? '답변 생성 모델'
                }
              >
                <option value="">
                  모델: {llmModels.find(m => m.id === llmDefault)?.label ?? '기본'} (기본)
                </option>
                {llmModels.map(m => (
                  <option key={m.id} value={m.id}>
                    모델: {m.label} · {m.note}
                  </option>
                ))}
              </select>
            )}
            {corpusVersions.length > 0 && (
              <select
                className="corpus-select"
                value={corpusVersion}
                onChange={e => handleCorpusChange(e.target.value)}
                disabled={!useInternalDocs}
                title="질의 대상 코퍼스 버전"
              >
                <option value="">
                  기본 (v{corpusVersions.find(c => c.is_active)?.version ?? '?'})
                </option>
                {corpusVersions.map(cv => (
                  <option key={cv.version} value={cv.version}>
                    코퍼스 v{cv.version} · {cv.doc_count}문서{cv.is_active ? ' (활성)' : ''}
                  </option>
                ))}
              </select>
            )}
          </div>
          {(attachments.length > 0 || uploading || attachError) && (
            <div className="attach-bar">
              {attachments.map(att => (
                <span key={att.id} className="attach-chip" title={att.filename}>
                  <FileText size={12} />
                  {att.filename}
                </span>
              ))}
              {uploading && <span className="attach-chip is-busy">첨부하는 중…</span>}
              {attachError && <span className="attach-err">{attachError}</span>}
            </div>
          )}
          <div className="input-box">
            <textarea
              ref={textareaRef}
              rows={1}
              placeholder="질문에 사업명을 반드시 포함해 주세요 (홍성 · 당진1 · 당진2 · 임자 · 안면도 · 태평)"
              value={input}
              onChange={handleTextareaInput}
              onKeyDown={handleKeyDown}
            />
            <input
              ref={fileInputRef}
              type="file"
              accept={ATTACH_ACCEPT}
              onChange={handleFileSelected}
              style={{ display: 'none' }}
            />
            <button
              className="icon-btn"
              title="파일 첨부 (PDF · Word · Excel · PPT · 한글)"
              onClick={handleAttachClick}
              disabled={uploading}
            >
              <Paperclip />
            </button>
            <button className="send-btn" title="전송" onClick={handleSend} disabled={sending}>
              <Send />
            </button>
          </div>
          <div className="composer-foot">
            답변은 참조 자료에 근거하며, 중요한 의사결정 전 원본 확인을 권장합니다.
          </div>
        </div>
      </div>
    </section>
  )
}
