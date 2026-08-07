import { useEffect, useRef, useState } from 'react'
import {
  MessageSquare, FileText, TrendingUp, LayoutDashboard, Plus, MessageCircle,
  MoreHorizontal, Pin, PinOff, Pencil, Trash2,
} from 'lucide-react'
import type { ViewType } from '../App'

interface SidebarProps {
  activeView: ViewType
  onNavigate: (view: ViewType) => void
  activeConversationId: string | null
  onSelectConversation: (id: string) => void
  onNewChat: () => void
  refreshKey: number
}

/** GET /api/conversations/ 응답 항목 (backend: ConversationSerializer) */
interface ConversationSummary {
  id: string
  title: string | null
  last_message_at: string | null
  is_pinned: boolean
}

const NAV_ITEMS: { view: ViewType; label: string; Icon: typeof MessageSquare }[] = [
  { view: 'chat',     label: '대화',                Icon: MessageSquare },
  { view: 'contract', label: '계약',                Icon: FileText },
  { view: 'finance',  label: '재무모델',            Icon: TrendingUp },
  { view: 'ops',      label: '운영관리 Dashboard',  Icon: LayoutDashboard },
]

export default function Sidebar({
  activeView, onNavigate, activeConversationId, onSelectConversation, onNewChat, refreshKey,
}: SidebarProps) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [menuFor, setMenuFor] = useState<string | null>(null)      // 점3개 메뉴가 열린 대화
  const [renamingId, setRenamingId] = useState<string | null>(null) // 이름 편집 중인 대화
  const [renameText, setRenameText] = useState('')
  const renameInputRef = useRef<HTMLInputElement>(null)

  const loadConversations = () => {
    setLoading(true)
    // 정렬은 서버가 담당한다 (고정 우선 → 최근 대화 → 빈 대화는 뒤로)
    return fetch('/api/conversations/', { credentials: 'include' })
      .then(res => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then(data => setConversations(Array.isArray(data) ? data : (data.results ?? [])))
      .catch(() => setConversations([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (activeView !== 'chat') return
    let cancelled = false
    setLoading(true)
    fetch('/api/conversations/', { credentials: 'include' })
      .then(res => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then(data => {
        if (cancelled) return
        setConversations(Array.isArray(data) ? data : (data.results ?? []))
      })
      .catch(() => { if (!cancelled) setConversations([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [activeView, refreshKey])

  // 메뉴가 열린 상태에서 바깥을 클릭하거나 Esc를 누르면 닫는다
  useEffect(() => {
    if (!menuFor) return
    const close = () => setMenuFor(null)
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') close() }
    document.addEventListener('click', close)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('click', close)
      document.removeEventListener('keydown', onKey)
    }
  }, [menuFor])

  useEffect(() => {
    if (renamingId) renameInputRef.current?.focus()
  }, [renamingId])

  const getCsrf = async (): Promise<string> => {
    const res = await fetch('/api/auth/csrf/', { credentials: 'include' })
    return (await res.json()).csrfToken
  }

  const patchConversation = async (id: string, body: Record<string, unknown>) => {
    const csrf = await getCsrf()
    const res = await fetch(`/api/conversations/${id}/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify(body),
      credentials: 'include',
    })
    if (!res.ok) throw new Error(String(res.status))
    return res.json()
  }

  const handleTogglePin = async (conv: ConversationSummary) => {
    setMenuFor(null)
    // 낙관적 갱신 후 서버 반영 — 실패하면 목록을 다시 읽어 되돌린다
    setConversations(prev => prev.map(c =>
      c.id === conv.id ? { ...c, is_pinned: !c.is_pinned } : c))
    try {
      await patchConversation(conv.id, { is_pinned: !conv.is_pinned })
    } catch { /* 아래 새로고침이 실제 상태로 되돌린다 */ }
    loadConversations()
  }

  const startRename = (conv: ConversationSummary) => {
    setMenuFor(null)
    setRenamingId(conv.id)
    setRenameText(conv.title || '')
  }

  const commitRename = async () => {
    const id = renamingId
    const title = renameText.trim()
    setRenamingId(null)
    if (!id || !title) return
    setConversations(prev => prev.map(c => (c.id === id ? { ...c, title } : c)))
    try {
      await patchConversation(id, { title })
    } catch { /* 실패 시 아래 새로고침으로 원복 */ }
    loadConversations()
  }

  const handleDelete = async (conv: ConversationSummary) => {
    setMenuFor(null)
    const name = conv.title || '제목 없는 대화'
    // 되돌릴 수 없는 작업이라 반드시 확인을 받는다
    if (!window.confirm(`"${name}" 대화를 삭제할까요?\n메시지와 출처 기록이 함께 삭제되며 되돌릴 수 없습니다.`)) return
    try {
      const csrf = await getCsrf()
      const res = await fetch(`/api/conversations/${conv.id}/`, {
        method: 'DELETE',
        headers: { 'X-CSRFToken': csrf },
        credentials: 'include',
      })
      if (!res.ok) throw new Error(String(res.status))
      setConversations(prev => prev.filter(c => c.id !== conv.id))
      // 보고 있던 대화를 지웠다면 빈 화면으로 되돌린다
      if (activeConversationId === conv.id) onNewChat()
    } catch {
      alert('삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.')
      loadConversations()
    }
  }

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="brand">
        <div className="mark">
          <svg viewBox="0 0 24 24" fill="none" stroke="#EAF7F1" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a7 7 0 0 0-7 7c0 3 2 5 4 7l3 6 3-6c2-2 4-4 4-7a7 7 0 0 0-7-7Z"/>
            <path d="M12 9v0"/>
            <path d="M9 9c1.5-1.5 4.5-1.5 6 0"/>
          </svg>
        </div>
        <div className="txt">
          <b>재생E AI Agent</b>
          <span>RENEWABLE ENERGY</span>
        </div>
      </div>

      {/* Navigation */}
      <div className="nav-label">메뉴</div>
      {NAV_ITEMS.map(({ view, label, Icon }) => (
        <button
          key={view}
          className={`nav-item ${activeView === view ? 'active' : ''}`}
          onClick={() => onNavigate(view)}
        >
          <Icon />
          {label}
        </button>
      ))}

      {/* Chat History (only visible on chat view) */}
      {activeView === 'chat' && (
        <div className="history">
          <button className="new-chat" onClick={onNewChat}>
            <Plus size={15} />
            새 대화
          </button>
          <div className="nav-label" style={{ paddingTop: 8 }}>대화 기록</div>
          {loading && conversations.length === 0 ? (
            <div className="h-empty">불러오는 중…</div>
          ) : conversations.length === 0 ? (
            <div className="h-empty">
              <MessageCircle size={14} />
              아직 대화 기록이 없습니다
            </div>
          ) : (
            conversations.map(conv => (
              <div
                key={conv.id}
                className={`h-item ${conv.id === activeConversationId ? 'active' : ''} ${menuFor === conv.id ? 'menu-open' : ''}`}
              >
                {renamingId === conv.id ? (
                  <input
                    ref={renameInputRef}
                    className="h-rename"
                    value={renameText}
                    onChange={e => setRenameText(e.target.value)}
                    onBlur={commitRename}
                    onKeyDown={e => {
                      if (e.key === 'Enter') commitRename()
                      if (e.key === 'Escape') setRenamingId(null)
                    }}
                    maxLength={300}
                  />
                ) : (
                  <>
                    <button
                      className="h-row"
                      onClick={() => onSelectConversation(conv.id)}
                      title={conv.title || '제목 없는 대화'}
                    >
                      {conv.is_pinned
                        ? <Pin size={13} className="h-pin" />
                        : <MessageCircle size={14} />}
                      <span className="h-title">{conv.title || '제목 없는 대화'}</span>
                    </button>

                    <button
                      className="h-more"
                      aria-label="대화 메뉴"
                      onClick={e => {
                        e.stopPropagation()   // 바깥 클릭 닫기 핸들러와 충돌 방지
                        setMenuFor(menuFor === conv.id ? null : conv.id)
                      }}
                    >
                      <MoreHorizontal size={15} />
                    </button>

                    {menuFor === conv.id && (
                      <div className="h-menu" onClick={e => e.stopPropagation()}>
                        <button onClick={() => handleTogglePin(conv)}>
                          {conv.is_pinned ? <PinOff size={14} /> : <Pin size={14} />}
                          {conv.is_pinned ? '고정 해제' : '고정'}
                        </button>
                        <button onClick={() => startRename(conv)}>
                          <Pencil size={14} />
                          이름 변경
                        </button>
                        <button className="danger" onClick={() => handleDelete(conv)}>
                          <Trash2 size={14} />
                          삭제
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* User */}
      <div className="side-foot">
        <div className="user-chip">
          <div className="av">관</div>
          <div className="u-txt">
            <b>AI Agent 관리자</b>
            <span>재생E 사업개발실</span>
          </div>
        </div>
      </div>
    </aside>
  )
}
