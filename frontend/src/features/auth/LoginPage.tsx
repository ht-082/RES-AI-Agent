import { useState, FormEvent } from 'react'

interface LoginPageProps {
  onLoginSuccess: (user: any) => void
}

export default function LoginPage({ onLoginSuccess }: LoginPageProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      // 1. CSRF 토큰 가져오기
      const csrfRes = await fetch('/api/auth/csrf/', { credentials: 'include' })
      const csrfData = await csrfRes.json()

      // 2. 로그인 요청
      const res = await fetch('/api/auth/login/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfData.csrfToken,
        },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.error || '로그인에 실패했습니다.')
        return
      }

      onLoginSuccess(data.user)
    } catch {
      setError('서버에 연결할 수 없습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-wrapper">
      <div className="login-card">
        {/* 로고 영역 */}
        <div className="login-logo">
          <div className="login-logo-icon">
            <svg viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="14" stroke="currentColor" strokeWidth="2" />
              <path d="M16 6 L16 26 M6 16 L26 16 M9 9 L23 23 M23 9 L9 23" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
              <circle cx="16" cy="16" r="4" fill="currentColor" />
            </svg>
          </div>
          <h1>재생E AI Agent</h1>
          <p>RENEWABLE ENERGY</p>
        </div>

        {/* 로그인 폼 */}
        <form onSubmit={handleSubmit} className="login-form">
          <label className="fld">
            <span className="lab">아이디</span>
            <input
              className="inp"
              type="text"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="아이디를 입력하세요 (예: admin)"
              autoFocus
              required
            />
          </label>

          <label className="fld">
            <span className="lab">비밀번호</span>
            <input
              className="inp"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="비밀번호를 입력하세요"
              required
            />
          </label>

          {error && (
            <div className="login-error">
              <svg viewBox="0 0 20 20" fill="currentColor" style={{ width: 16, height: 16, flexShrink: 0 }}>
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
              </svg>
              {error}
            </div>
          )}

          <button type="submit" className="btn-primary login-btn" disabled={loading}>
            {loading ? (
              <span className="login-spinner" />
            ) : (
              <>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 18, height: 18 }}>
                  <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
                  <polyline points="10 17 15 12 10 7" />
                  <line x1="15" y1="12" x2="3" y2="12" />
                </svg>
                로그인
              </>
            )}
          </button>
        </form>

        <div className="login-footer">
          <span>재생E 사업개발실 전용 시스템</span>
        </div>
      </div>
    </div>
  )
}
