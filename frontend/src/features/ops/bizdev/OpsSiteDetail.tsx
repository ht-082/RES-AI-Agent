import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, Zap } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import SiteListRail from './SiteListRail'
import OverviewCard from './detail/OverviewCard'
import FactSection from './detail/FactSection'
import ContractSection from './detail/ContractSection'
import EventSection from './detail/EventSection'
import GridCard from './detail/GridCard'
import { apiGet } from './api'
import { formatKRW } from './constants'
import AliasBadge from './detail/AliasBadge'
import type { SiteDetailPayload } from './types'
import type { DetailProps } from './SiteDetail'

// 월별 발전량 분포 계수 — 실측 데이터가 없어 연간 예상 발전량(annual_gwh)을
// 국내 태양광 일사량 계절 패턴으로 배분한 "추정치"다. 실시간 연동은 후속.
const MONTH_WEIGHT = [0.062, 0.070, 0.090, 0.098, 0.104, 0.096,
                     0.086, 0.088, 0.084, 0.082, 0.070, 0.070]

// 운영 사업 상세 — lifecycle='ops' 전용. 인허가 대신 발전 실적·경제성 중심.
export default function OpsSiteDetail({ siteId, sites, user, onBack, onSelectSite, onSitesChanged }: DetailProps) {
  const [data, setData] = useState<SiteDetailPayload | null>(null)
  const [error, setError] = useState('')

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

  const annual = data?.site.annual_gwh ? Number(data.site.annual_gwh) : 0
  const chartData = MONTH_WEIGHT.map((w, i) => ({
    month: `${i + 1}월`,
    추정발전량: Math.round(annual * w * 10) / 10,
  }))
  const canEdit = data?.site.can_edit ?? false
  const factsOf = (section: string) => (data?.facts || []).filter(f => f.section === section)
  const labelOf = (key: string) => data?.sections.find(s => s.key === key)?.label || key
  void user

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
            <span style={{ fontSize: 13, color: 'var(--ink-faint)', fontWeight: 500 }}>운영 사업 상세</span>
          </h2>
          <p>상업운전 중 자산 — 발전 실적·경제성 중심 (실시간 계측 연동은 후속)</p>
        </div>
      </div>
      {error && <p className="note" style={{ color: 'var(--red)' }}>{error}</p>}

      <div style={{ display: 'grid', gridTemplateColumns: '190px minmax(0, 1fr)', gap: 16, alignItems: 'start' }}>
        <SiteListRail sites={sites} selectedId={siteId} onSelect={onSelectSite} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0 }}>
          {!data && !error && <p className="note">불러오는 중...</p>}
          {data && (
            <>
              <div className="kpi-row">
                <div className="kpi">
                  <div className="k-lab"><Zap size={15} /> 설비용량</div>
                  <div className="k-val">{Math.round(Number(data.site.capacity_mw))}<span className="u">MW</span></div>
                  <div className="k-sub">{data.site.facility_type || '-'}</div>
                </div>
                <div className="kpi">
                  <div className="k-lab"><Zap size={15} /> 연간 예상 발전량</div>
                  <div className="k-val">{annual || '-'}<span className="u">GWh</span></div>
                  <div className="k-sub">등록 기준값</div>
                </div>
                <div className="kpi">
                  <div className="k-lab"><Zap size={15} /> 상업운전</div>
                  <div className="k-val" style={{ fontSize: 20 }}>{data.site.cod || '운영중'}</div>
                  <div className="k-sub">담당 {data.site.pm_name || '-'}</div>
                </div>
                <div className="kpi">
                  <div className="k-lab"><Zap size={15} /> 투자비(승인 예산)</div>
                  <div className="k-val" style={{ fontSize: 20 }}>{formatKRW(data.site.approved_budget_krw)}</div>
                  <div className="k-sub">집행 {formatKRW(data.budget_summary.total)}</div>
                </div>
              </div>

              <OverviewCard site={data.site} budget={data.budget_summary} />

              <div className="card block">
                <h3>월별 발전량 (추정)</h3>
                <div className="h-sub" style={{ marginBottom: 12 }}>
                  연간 예상 발전량 {annual}GWh 를 계절 패턴으로 배분한 추정치 — 실측 계측 연동은 후속
                </div>
                <div style={{ width: '100%', height: 240 }}>
                  <ResponsiveContainer>
                    <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -14 }}>
                      <CartesianGrid stroke="var(--line)" vertical={false} />
                      <XAxis dataKey="month" tick={{ fontSize: 11 }} stroke="var(--ink-faint)" />
                      <YAxis tick={{ fontSize: 11 }} stroke="var(--ink-faint)" />
                      <Tooltip formatter={(v) => [`${v ?? 0} GWh`, '추정 발전량']} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="추정발전량" fill="var(--green-accent)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <FactSection title={labelOf('basic')} facts={factsOf('basic')}
                           canEdit={canEdit} onChanged={reload} />
              <FactSection title={labelOf('spc')} facts={factsOf('spc')}
                           canEdit={canEdit} onChanged={reload} />
              <FactSection title={labelOf('econ')} facts={factsOf('econ')}
                           canEdit={canEdit} onChanged={reload} />
              <FactSection title={labelOf('pf')} facts={factsOf('pf')}
                           canEdit={canEdit} onChanged={reload} />
              <ContractSection siteId={siteId} contracts={data.contracts}
                               canEdit={canEdit} onChanged={reload} onError={setError} />
              <EventSection siteId={siteId} events={data.events}
                            canEdit={canEdit} onChanged={reload} onError={setError} />
              <GridCard sido={data.site.sido || data.site.location} />
            </>
          )}
        </div>
      </div>
    </section>
  )
}
