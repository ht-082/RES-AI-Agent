import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, Trash2 } from 'lucide-react'
import SiteListRail from './SiteListRail'
import OverviewSection from './detail/OverviewSection'
import FactSection from './detail/FactSection'
import RegistryImport from './detail/RegistryImport'
import PermitSection from './detail/PermitSection'
import EconSection from './detail/EconSection'
import SectionJump from './detail/SectionJump'
import ContractSection from './detail/ContractSection'
import EventSection from './detail/EventSection'
import BudgetCard from './detail/BudgetCard'
import GridCard from './detail/GridCard'
import OrdinanceCard from './detail/OrdinanceCard'
import { apiGet, apiSend } from './api'
import AliasBadge from './detail/AliasBadge'
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

  return (
    <section className="pane" style={{ flex: 1, overflowY: 'auto' }}>
      <div className="section-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 10 }}>
        <div>
          <button className="btn-ghost" style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 6, padding: '4px 8px' }} onClick={onBack}>
            <ArrowLeft size={14} /> 대시보드
          </button>
          <h2>
            {data?.site.name || '...'}{' '}
            <AliasBadge facts={data?.facts} />{' '}
            <span style={{ fontSize: 13, color: 'var(--ink-faint)', fontWeight: 500 }}>개발 사업 상세</span>
          </h2>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {isAdmin && data && (
            <button className="btn-ghost" style={{ color: 'var(--red)', display: 'flex', alignItems: 'center', gap: 5 }} onClick={removeSite}>
              <Trash2 size={14} /> 사업 삭제
            </button>
          )}
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
                { id: 'sec-basic', label: labelOf('basic') },
                { id: 'sec-spc', label: labelOf('spc') },
                { id: 'sec-land', label: labelOf('land') },
                { id: 'sec-budget', label: '예산 승인 · 집행' },
                { id: 'sec-contract', label: '계약 정보' },
                { id: 'sec-econ', label: labelOf('econ') },
                { id: 'sec-event', label: '진행경과 및 이슈' },
                { id: 'sec-permit', label: '인허가 현황' },
                { id: 'sec-pf', label: labelOf('pf') },
                { id: 'sec-grid', label: '계통 상황' },
                { id: 'sec-ordinance', label: '조례 모니터링' },
              ]} />

              {/* 사업 개요(기본 정보 + 부지 지도)를 왼쪽 절반에.
                  오른쪽 칸은 SPC 정보 자리로 비워 둔다. */}
              {/* 좌: 사업 개요 · 우: SPC 정보 + 부지 정보.
                  두 열의 아래 끝이 맞도록 stretch 시킨다. */}
              <div className="grid-2 bz-even-row">
                <OverviewSection id="sec-basic" site={data.site} facts={factsOf('basic')}
                                 canEdit={canEdit} onChanged={reload} />
                <div className="bz-stack">
                  <FactSection id="sec-spc" title={labelOf('spc')} facts={factsOf('spc')}
                               canEdit={canEdit} onChanged={reload}
                               modalExtra={canEdit
                                 ? <RegistryImport siteId={siteId} onDone={reload} />
                                 : undefined} />
                  <FactSection id="sec-land" title={labelOf('land')} facts={factsOf('land')}
                               canEdit={canEdit} onChanged={reload} />
                </div>
              </div>
              {/* 2×2 격자 — 나란히 놓인 짝끼리 높이가 같아야 하므로
                  열마다 쌓지 않고 한 격자에 네 카드를 넣는다(격자 행이 짝을 맞춘다).
                    예산 승인·집행 ↔ 계약 정보 / 경제성 ↔ 진행경과 및 이슈 */}
              <div className="grid-2 bz-even-row">
                <BudgetCard id="sec-budget" siteId={siteId} entries={data.budget_entries}
                            approvals={data.budget_approvals} summary={data.budget_summary}
                            canEdit={canEdit} onChanged={reload} />
                <ContractSection id="sec-contract" siteId={siteId} contracts={data.contracts}
                                 canEdit={canEdit} onChanged={reload} onError={setError} />
                <EconSection id="sec-econ" title={labelOf('econ')} facts={factsOf('econ')}
                             capacityMw={Number(data.site.capacity_mw) || undefined}
                             canEdit={canEdit} onChanged={reload} />
                <EventSection id="sec-event" siteId={siteId} events={data.events}
                              canEdit={canEdit} onChanged={reload} onError={setError} />
              </div>
              <PermitSection id="sec-permit" siteId={siteId} stages={data.stages} canEdit={canEdit}
                             onChanged={reload} onError={setError} />
              <FactSection id="sec-pf" title={labelOf('pf')} facts={factsOf('pf')}
                           canEdit={canEdit} onChanged={reload} />

              <div className="grid-2 bz-even-row">
                <GridCard id="sec-grid" sido={data.site.sido || data.site.location} />
                <OrdinanceCard id="sec-ordinance" sido={data.site.sido || data.site.location} />
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  )
}
