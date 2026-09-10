import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import SiteListRail from './SiteListRail'
import OverviewSection from './detail/OverviewSection'
import FactSection from './detail/FactSection'
import ContractSection from './detail/ContractSection'
import EventSection from './detail/EventSection'
import GridCard from './detail/GridCard'
import OpsPerformance from './detail/OpsPerformance'
import OpsPlanCard from './detail/OpsPlanCard'
import DefectCard from './detail/DefectCard'
import DocumentVault from './detail/DocumentVault'
import SectionJump from './detail/SectionJump'
import ScrollTopButton from './detail/ScrollTopButton'
import AliasBadge from './detail/AliasBadge'
import { apiGet } from './api'
import type { SiteDetailPayload } from './types'
import type { DetailProps } from './SiteDetail'

// 운영 사업 상세 — lifecycle='ops' 전용. 문서 '운영PJT Dashboard' 를 따른다.
//   1. 운영 현황  발전·재무 실적 / 정기 운영관리 계획 / 하자 보수 / 진행경과
//   2. SPC 현황   사업 기본 정보 / SPC 정보 / 재무지표 / 부지 정보 / 계약 정보
//   3. 문서 보관함 운영 · 법인문서 · 인허가 · 재무
export default function OpsSiteDetail({ siteId, sites, user, onBack, onSelectSite, onSitesChanged }: DetailProps) {
  const [data, setData] = useState<SiteDetailPayload | null>(null)
  const [error, setError] = useState('')
  const paneRef = useRef<HTMLElement>(null)

  const reload = useCallback(async () => {
    try {
      setData(await apiGet<SiteDetailPayload>(`/api/bizdev/sites/${siteId}/detail/`))
      onSitesChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : '오류')
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

  const canEdit = data?.site.can_edit ?? false
  const factsOf = (section: string) => (data?.facts || []).filter(f => f.section === section)
  const labelOf = (key: string) => data?.sections.find(s => s.key === key)?.label || key
  void user

  return (
    <section className="pane" ref={paneRef} style={{ flex: 1, overflowY: 'auto' }}>
      <div className="section-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 10 }}>
        <div>
          <button className="btn-ghost" style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 6, padding: '4px 8px' }} onClick={onBack}>
            <ArrowLeft size={14} /> 대시보드
          </button>
          <h2>
            {data?.site.name || '...'}{' '}
            <AliasBadge facts={data?.facts} />{' '}
            <span style={{ fontSize: 13, color: 'var(--ink-faint)', fontWeight: 500 }}>운영 사업 상세</span>
          </h2>
        </div>
      </div>
      {error && <p className="note" style={{ color: 'var(--red)' }}>{error}</p>}

      <div style={{ display: 'grid', gridTemplateColumns: '190px minmax(0, 1fr)', gap: 16, alignItems: 'start' }}>
        <SiteListRail sites={sites} selectedId={siteId} onSelect={onSelectSite} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0 }}>
          {!data && !error && <p className="note">불러오는 중...</p>}
          {data && (
            <>
              <SectionJump targets={[
                { id: 'ops-perf', label: '발전 · 재무 실적' },
                { id: 'ops-plan', label: '운영관리 계획' },
                { id: 'ops-defect', label: '하자 보수' },
                { id: 'ops-event', label: '진행경과 및 이슈' },
                { id: 'ops-basic', label: labelOf('basic') },
                { id: 'ops-spc', label: labelOf('spc') },
                { id: 'ops-fin', label: labelOf('fin') },
                { id: 'ops-land', label: labelOf('land') },
                { id: 'ops-contract', label: '계약 정보' },
                { id: 'ops-vault', label: '문서 보관함' },
                { id: 'ops-grid', label: '계통 상황' },
              ]} />

              {/* 1. 운영 현황 */}
              <h3 className="bz-part-title">1. 운영 현황</h3>
              <OpsPerformance id="ops-perf" rows={data.ops_daily} />
              <div className="grid-2 bz-even-row">
                <OpsPlanCard id="ops-plan" siteId={siteId} plans={data.ops_plans}
                             canEdit={canEdit} onChanged={reload} onError={setError} />
                <DefectCard id="ops-defect" siteId={siteId} defects={data.defects}
                            canEdit={canEdit} onChanged={reload} onError={setError} />
              </div>
              <EventSection id="ops-event" siteId={siteId} events={data.events}
                            canEdit={canEdit} onChanged={reload} onError={setError} />

              {/* 2. SPC 현황 */}
              <h3 className="bz-part-title">2. SPC 현황</h3>
              <div className="grid-2 bz-even-row">
                <OverviewSection id="ops-basic" site={data.site} facts={factsOf('basic')}
                                 canEdit={canEdit} onChanged={reload} />
                <div className="bz-stack">
                  <FactSection id="ops-spc" title={labelOf('spc')} facts={factsOf('spc')}
                               canEdit={canEdit} onChanged={reload} />
                  <FactSection id="ops-land" title={labelOf('land')} facts={factsOf('land')}
                               canEdit={canEdit} onChanged={reload} />
                </div>
              </div>
              <div className="grid-2 bz-even-row">
                <FactSection id="ops-fin" title={labelOf('fin')} facts={factsOf('fin')}
                             canEdit={canEdit} onChanged={reload} showNote />
                <ContractSection id="ops-contract" siteId={siteId} contracts={data.contracts}
                                 canEdit={canEdit} onChanged={reload} onError={setError} />
              </div>

              {/* 3. 문서 보관함 */}
              <h3 className="bz-part-title">3. 문서 보관함</h3>
              <DocumentVault id="ops-vault" siteId={siteId} docs={data.site_documents}
                             canEdit={canEdit} onChanged={reload} onError={setError} />
              <GridCard id="ops-grid" sido={data.site.sido || data.site.location} />
            </>
          )}
        </div>
      </div>
      <ScrollTopButton containerRef={paneRef} />
    </section>
  )
}
