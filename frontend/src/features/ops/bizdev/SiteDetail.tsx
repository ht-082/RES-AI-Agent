import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, Pencil, Trash2 } from 'lucide-react'
import SiteFormModal from './SiteFormModal'
import SiteListRail from './SiteListRail'
import OverviewSection from './detail/OverviewSection'
import FactSection from './detail/FactSection'
import PermitSection from './detail/PermitSection'
import ContractSection from './detail/ContractSection'
import EventSection from './detail/EventSection'
import BudgetCard from './detail/BudgetCard'
import GridCard from './detail/GridCard'
import OrdinanceCard from './detail/OrdinanceCard'
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

// 개발 사업 상세 — 사업개요 양식(docs 사업개요_양식_v3.md) 목차 순서로 구성.
// 양식에 없는 예산 집행·계통·조례는 뒤에 유지한다(사용자 결정).
export default function SiteDetail({ siteId, sites, user, onBack, onSelectSite, onSitesChanged }: DetailProps) {
  const [data, setData] = useState<SiteDetailPayload | null>(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)

  const reload = useCallback(async () => {
    try {
      setError('')
      setData(await apiGet<SiteDetailPayload>(`/api/bizdev/sites/${siteId}/detail/`))
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
    if (!confirm(`"${data.site.name}" 사업을 삭제할까요? 인허가·계약·경과·문서가 모두 삭제됩니다.`)) return
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
  const factsOf = (section: string) => (data?.facts || []).filter(f => f.section === section)
  const labelOf = (key: string) => data?.sections.find(s => s.key === key)?.label || key
  const confirmed = (data?.facts || []).filter(f => f.certainty === 'confirmed').length
  const unconfirmed = (data?.facts || []).filter(f => f.certainty === 'unconfirmed').length

  return (
    <section className="pane" style={{ flex: 1, overflowY: 'auto' }}>
      <div className="section-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 10 }}>
        <div>
          <button className="btn-ghost" style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 6, padding: '4px 8px' }} onClick={onBack}>
            <ArrowLeft size={14} /> 대시보드
          </button>
          <h2>
            {data?.site.name || '...'}{' '}
            <span style={{ fontSize: 13, color: 'var(--ink-faint)', fontWeight: 500 }}>개발 사업 상세</span>
          </h2>
          {data && (
            <p style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
              <span className="bz-chip" style={{ background: 'var(--mint-soft)', color: 'var(--green-600)' }}>
                확정 {confirmed}
              </span>
              <span className="bz-chip" style={{ background: 'var(--amber-soft)', color: 'var(--amber)' }}>
                미확정 {unconfirmed}
              </span>
              <span style={{ color: 'var(--ink-faint)' }}>
                인허가 진척 {data.site.overall_pct}% · 담당 {data.site.pm_name || '-'}
              </span>
            </p>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {canEdit && data && (
            <button className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 5 }}
                    onClick={() => setEditing(true)}>
              <Pencil size={14} /> 집계 정보 수정
            </button>
          )}
          {isAdmin && data && (
            <button className="btn-ghost" style={{ color: 'var(--red)', display: 'flex', alignItems: 'center', gap: 5 }} onClick={removeSite}>
              <Trash2 size={14} /> 사업 삭제
            </button>
          )}
        </div>
      </div>
      {error && <p className="note" style={{ color: 'var(--red)' }}>{error}</p>}

      {editing && data && (
        <SiteFormModal site={data.site} onClose={() => setEditing(false)} onSaved={reload} />
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '190px minmax(0, 1fr)', gap: 16, alignItems: 'start' }}>
        <SiteListRail sites={sites} selectedId={siteId} onSelect={onSelectSite} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0 }}>
          {!data && !error && <p className="note">불러오는 중...</p>}
          {data && (
            <>
              {/* 사업 개요(기본 정보 + 부지 지도)를 왼쪽 절반에.
                  오른쪽 칸은 SPC 정보 자리로 비워 둔다. */}
              <div className="grid-2 lean" style={{ alignItems: 'start' }}>
                <OverviewSection site={data.site} facts={factsOf('basic')}
                                 canEdit={canEdit} onChanged={reload} />
              </div>
              <FactSection title={labelOf('spc')} facts={factsOf('spc')}
                           canEdit={canEdit} onChanged={reload} />
              <PermitSection stages={data.stages} canEdit={canEdit}
                             onChanged={reload} onError={setError} />
              <FactSection title={labelOf('land')} facts={factsOf('land')}
                           canEdit={canEdit} onChanged={reload} />
              <ContractSection siteId={siteId} contracts={data.contracts}
                               canEdit={canEdit} onChanged={reload} onError={setError} />
              <EventSection siteId={siteId} events={data.events}
                            canEdit={canEdit} onChanged={reload} onError={setError} />
              <FactSection title={labelOf('econ')} facts={factsOf('econ')}
                           canEdit={canEdit} onChanged={reload} />
              <FactSection title={labelOf('pf')} facts={factsOf('pf')}
                           canEdit={canEdit} onChanged={reload} />

              {/* 양식에 없는 유지 기능 */}
              <BudgetCard siteId={siteId} entries={data.budget_entries}
                          summary={data.budget_summary} canEdit={canEdit} onChanged={reload} />
              <div className="grid-2 lean">
                <GridCard sido={data.site.sido || data.site.location} />
                <OrdinanceCard sido={data.site.sido || data.site.location} />
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  )
}
