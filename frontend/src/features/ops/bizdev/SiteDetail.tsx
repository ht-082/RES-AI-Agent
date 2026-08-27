import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, Trash2 } from 'lucide-react'
import SiteListRail from './SiteListRail'
import OverviewCard from './detail/OverviewCard'
import SpcCard from './detail/SpcCard'
import BudgetCard from './detail/BudgetCard'
import IssueCard from './detail/IssueCard'
import GridCard from './detail/GridCard'
import OrdinanceCard from './detail/OrdinanceCard'
import PermitStagesCard from './detail/PermitStagesCard'
import { apiGet, apiSend } from './api'
import type { AppUser, Site, SiteDetailPayload } from './types'

export interface DetailProps {
  siteId: string
  sites: Site[]
  user: AppUser | null
  onBack: () => void
  onSelectSite: (id: string) => void
  onSitesChanged: () => void
}

// 개발 사업 상세 — 원본 project.html 이식 (인허가·예산 중심)
export default function SiteDetail({ siteId, sites, user, onBack, onSelectSite, onSitesChanged }: DetailProps) {
  const [data, setData] = useState<SiteDetailPayload | null>(null)
  const [error, setError] = useState('')

  const reload = useCallback(async () => {
    try {
      setError('')
      const d = await apiGet<SiteDetailPayload>(`/api/bizdev/sites/${siteId}/detail/`)
      setData(d)
      onSitesChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : '상세를 불러오지 못했습니다.')
    }
  }, [siteId, onSitesChanged])

  useEffect(() => {
    let cancelled = false
    setData(null)
    apiGet<SiteDetailPayload>(`/api/bizdev/sites/${siteId}/detail/`)
      .then(d => { if (!cancelled) setData(d) })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : '오류') })
    return () => { cancelled = true }
  }, [siteId])

  const removeSite = async () => {
    if (!data) return
    if (!confirm(`"${data.site.name}" 사업지를 삭제할까요? 단계·문서·예산·이슈가 모두 삭제됩니다.`)) return
    try {
      await apiSend('DELETE', `/api/bizdev/sites/${siteId}/`)
      onSitesChanged()
      onBack()
    } catch (e) {
      setError(e instanceof Error ? e.message : '삭제 실패')
    }
  }

  const canEdit = data?.site.can_edit ?? false
  const isAdmin = user?.role === 'admin'

  return (
    <section className="pane" style={{ flex: 1, overflowY: 'auto' }}>
      <div className="section-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 10 }}>
        <div>
          <button className="btn-ghost" style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 6, padding: '4px 8px' }} onClick={onBack}>
            <ArrowLeft size={14} /> 대시보드
          </button>
          <h2>{data?.site.name || '...'} <span style={{ fontSize: 13, color: 'var(--ink-faint)', fontWeight: 500 }}>개발 사업 상세</span></h2>
        </div>
        {isAdmin && data && (
          <button className="btn-ghost" style={{ color: 'var(--red)', display: 'flex', alignItems: 'center', gap: 5 }} onClick={removeSite}>
            <Trash2 size={14} /> 사업지 삭제
          </button>
        )}
      </div>
      {error && <p className="note" style={{ color: 'var(--red)' }}>{error}</p>}

      <div style={{ display: 'grid', gridTemplateColumns: '190px minmax(0, 1fr)', gap: 16, alignItems: 'start' }}>
        <SiteListRail sites={sites} selectedId={siteId} onSelect={onSelectSite} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0 }}>
          {!data && !error && <p className="note">불러오는 중...</p>}
          {data && (
            <>
              <OverviewCard site={data.site} budget={data.budget_summary} />
              <div className="grid-2 lean">
                <SpcCard site={data.site} />
                <IssueCard siteId={siteId} issues={data.issues} canEdit={canEdit} onChanged={reload} />
              </div>
              <BudgetCard siteId={siteId} entries={data.budget_entries}
                          summary={data.budget_summary} canEdit={canEdit} onChanged={reload} />
              <div className="grid-2 lean">
                <GridCard sido={data.site.sido || data.site.location} />
                <OrdinanceCard sido={data.site.sido || data.site.location} />
              </div>
              <PermitStagesCard siteId={siteId} stages={data.stages} canEdit={canEdit} onChanged={reload} />
            </>
          )}
        </div>
      </div>
    </section>
  )
}
