import { useCallback, useEffect, useState } from 'react'
import BizdevDashboard from './BizdevDashboard'
import SiteDetail from './SiteDetail'
import OpsSiteDetail from './OpsSiteDetail'
import { apiGet } from './api'
import type { AppUser, Site } from './types'

// 사업개발 탭 루트 — 라우터 없이 state 로 대시보드 ↔ 상세 전환(기존 관례).
// 상세 진입 시 lifecycle 에 따라 분기: dev → 개발 상세, ops → 운영 상세.
export default function BizdevTab({ user }: { user: AppUser | null }) {
  const [sites, setSites] = useState<Site[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const reload = useCallback(async () => {
    try {
      setError('')
      setSites(await apiGet<Site[]>('/api/bizdev/sites/'))
    } catch (e) {
      setError(e instanceof Error ? e.message : '사업지 목록을 불러오지 못했습니다.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    apiGet<Site[]>('/api/bizdev/sites/')
      .then(data => { if (!cancelled) setSites(data) })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : '오류') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return <section className="pane" style={{ flex: 1 }}><p className="note">사업지 목록을 불러오는 중...</p></section>
  }
  if (error) {
    return <section className="pane" style={{ flex: 1 }}><p className="note" style={{ color: 'var(--red)' }}>{error}</p></section>
  }

  const selected = sites.find(s => s.id === selectedId) || null
  if (selected) {
    const DetailView = selected.lifecycle === 'ops' ? OpsSiteDetail : SiteDetail
    return (
      <DetailView
        siteId={selected.id}
        sites={sites}
        user={user}
        onBack={() => setSelectedId(null)}
        onSelectSite={setSelectedId}
        onSitesChanged={reload}
      />
    )
  }

  return (
    <BizdevDashboard
      sites={sites}
      user={user}
      onSelectSite={setSelectedId}
      onSitesChanged={reload}
    />
  )
}
