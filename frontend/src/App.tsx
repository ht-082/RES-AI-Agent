import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'
import ChatView from './features/chat/ChatView'
import ContractView from './features/contracts/ContractView'
import FinanceView from './features/finance/FinanceView'
import OpsView from './features/ops/OpsView'
import LoginPage from './features/auth/LoginPage'

export type ViewType = 'chat' | 'contract' | 'finance' | 'ops'

const VIEW_META: Record<ViewType, { title: string; sub: string }> = {
  chat:     { title: '대화',                sub: '사내 자료 기반 질의응답' },
  contract: { title: '계약',                sub: '계약서 생성 및 검토' },
  finance:  { title: '재무모델',            sub: '재무모델 생성 및 검토' },
  ops:      { title: '사업 관리 Dashboard', sub: '개발·운영 자산 통합 파이프라인' },
}

export default function App() {
  const [user, setUser] = useState<any>(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [activeView, setActiveView] = useState<ViewType>('chat')
  // 대화 선택 상태는 App이 보유한다. ChatView 안에 두면 탭을 옮길 때 언마운트되어 사라진다.
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  // 사이드바 목록 재조회 트리거 (새 대화 생성 / 제목 확정 시 증가)
  const [convRefreshKey, setConvRefreshKey] = useState(0)

  const handleConversationChanged = (id: string) => {
    setActiveConversationId(id)
    setConvRefreshKey(k => k + 1)
  }

  // 페이지 로드 시 세션 유효성 확인
  useEffect(() => {
    fetch('/api/auth/me/', { credentials: 'include' })
      .then(res => {
        if (res.ok) return res.json()
        throw new Error('not authenticated')
      })
      .then(data => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setAuthChecked(true))
  }, [])

  // 아직 인증 확인 중이면 로딩 표시
  if (!authChecked) {
    return (
      <div className="login-wrapper">
        <div className="login-card" style={{ textAlign: 'center', padding: 60 }}>
          <div className="login-spinner" />
          <p style={{ marginTop: 16, color: 'var(--ink-soft)' }}>세션 확인 중...</p>
        </div>
      </div>
    )
  }

  // 미인증 → 로그인 페이지
  if (!user) {
    return <LoginPage onLoginSuccess={setUser} />
  }

  // 인증됨 → 메인 앱
  const meta = VIEW_META[activeView]

  return (
    <>
      <Sidebar
        activeView={activeView}
        onNavigate={setActiveView}
        activeConversationId={activeConversationId}
        onSelectConversation={setActiveConversationId}
        onNewChat={() => setActiveConversationId(null)}
        refreshKey={convRefreshKey}
      />
      <main className="main">
        <Topbar title={meta.title} subtitle={meta.sub} activeView={activeView} user={user} />
        {activeView === 'chat'     && (
          <ChatView
            conversationId={activeConversationId}
            onConversationChanged={handleConversationChanged}
          />
        )}
        {activeView === 'contract' && <ContractView />}
        {activeView === 'finance'  && <FinanceView />}
        {activeView === 'ops'      && <OpsView user={user} />}
      </main>
    </>
  )
}
