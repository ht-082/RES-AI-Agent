import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import SiteListRail from './SiteListRail'
import OverviewSection from './detail/OverviewSection'
import FactSection from './detail/FactSection'
import ContractSection from './detail/ContractSection'
import EventSection from './detail/EventSection'
import GridCard from './detail/GridCard'
import OrdinanceCard from './detail/OrdinanceCard'
import OpsPerformance from './detail/OpsPerformance'
import OpsPlanCard from './detail/OpsPlanCard'
import DefectCard from './detail/DefectCard'
import SectionJump from './detail/SectionJump'
import ScrollTopButton from './detail/ScrollTopButton'
import AliasBadge from './detail/AliasBadge'
import { apiGet } from './api'
import type { SiteDetailPayload } from './types'
import type { DetailProps } from './SiteDetail'

// 운영 사업 상세 — lifecycle='ops' 전용. 문서 '운영PJT Dashboard' 의 항목을
// 담되 배치는 개발 상세와 맞춘다(사업 개요 · SPC · 부지가 맨 위).
//   사업 개요 | SPC · 부지  →  진행경과 | 계약  →  발전·재무 실적  →
//   운영관리 계획 | 하자 보수  →  재무지표  →  계통 상황 | 조례 모니터링
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
                { id: 'ops-basic', label: labelOf('basic') },
                { id: 'ops-spc', label: labelOf('spc') },
                { id: 'ops-land', label: labelOf('land') },
                { id: 'ops-event', label: '진행경과 및 이슈' },
                { id: 'ops-contract', label: '계약 정보' },
                { id: 'ops-perf', label: '발전 · 재무 실적' },
                { id: 'ops-plan', label: '운영관리 계획' },
                { id: 'ops-defect', label: '하자 보수' },
                { id: 'ops-fin', label: labelOf('fin') },
                { id: 'ops-grid', label: '계통 상황' },
                { id: 'ops-law', label: '조례 모니터링' },
              ]} />

              {/* 좌: 사업 개요 · 우: SPC 정보 + 부지 정보 (개발 상세와 같은 배치) */}
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
                <EventSection id="ops-event" siteId={siteId} events={data.events}
                              canEdit={canEdit} onChanged={reload} onError={setError} />
                <ContractSection id="ops-contract" siteId={siteId} contracts={data.contracts}
                                 canEdit={canEdit} onChanged={reload} onError={setError} />
              </div>

              <OpsPerformance id="ops-perf" rows={data.ops_daily} />
              <div className="grid-2 bz-even-row">
                <OpsPlanCard id="ops-plan" siteId={siteId} plans={data.ops_plans}
                             canEdit={canEdit} onChanged={reload} onError={setError} />
                <DefectCard id="ops-defect" siteId={siteId} defects={data.defects}
                            canEdit={canEdit} onChanged={reload} onError={setError} />
              </div>

              <FactSection id="ops-fin" title={labelOf('fin')} facts={factsOf('fin')}
                           canEdit={canEdit} onChanged={reload} showNote />
              {/* 맨 아래 행 — 개발 상세와 같은 짝(계통 · 조례) */}
              <div className="grid-2 bz-even-row">
                <GridCard id="ops-grid" sido={data.site.sido || data.site.location} />
                <OrdinanceCard id="ops-law" sido={data.site.sido || data.site.location} />
              </div>
            </>
          )}
        </div>
      </div>
      <ScrollTopButton containerRef={paneRef} />
    </section>
  )
}
