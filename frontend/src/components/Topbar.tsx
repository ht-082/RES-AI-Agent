import { MessageSquare, FileText, TrendingUp, LayoutDashboard, LogOut } from 'lucide-react'
import type { ViewType } from '../App'

interface TopbarProps {
  title: string
  subtitle: string
  activeView: ViewType
  user?: { name: string; email: string; role: string }
}

const VIEW_ICONS: Record<ViewType, typeof MessageSquare> = {
  chat: MessageSquare,
  contract: FileText,
  finance: TrendingUp,
  ops: LayoutDashboard,
}

export default function Topbar({ title, subtitle, activeView, user }: TopbarProps) {
  const Icon = VIEW_ICONS[activeView]

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/logout/', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })
    } catch { /* ignore */ }
    window.location.reload()
  }

  return (
    <div className="topbar">
      <div className="t-title">
        <div className="t-ic">
          <Icon size={17} />
        </div>
        <div>
          <h1>{title}</h1>
          <div className="t-sub">{subtitle}</div>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        {user && (
          <div className="admin-badge" style={{ cursor: 'default' }}>
            <span className="dot" />
            {user.name || user.email} · {user.role === 'admin' ? '관리자' : '멤버'}
          </div>
        )}
        {user && (
          <button
            onClick={handleLogout}
            className="btn-ghost"
            style={{ fontSize: 12, gap: 5, padding: '5px 10px' }}
            title="로그아웃"
          >
            <LogOut size={14} />
            로그아웃
          </button>
        )}
      </div>
    </div>
  )
}
