import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Landmark, Plus, Scale, Sun } from 'lucide-react'
import SiteMap from './SiteMap'
import SiteDrawer from './SiteDrawer'
import GridRail from './GridRail'
import LawRail from './LawRail'
import PipelineTable from './PipelineTable'
import SiteFormModal from './SiteFormModal'
import { apiGet } from './api'
import { TOTAL_PIPELINE } from './constants'
import type { AppUser, Law, Site } from './types'

interface Summary {
  monthly_pending_issues: { total: number; by: { complaint: number; grid: number; etc: number } }
}

// 사업개발 메인 대시보드 — 원본 index.html 이식
export default function BizdevDashboard({ sites, onSelectSite, onSitesChanged }: {
  sites: Site[]
  user: AppUser | null
  onSelectSite: (id: string) => void
  onSitesChanged: () => void
}) {
  const [laws, setLaws] = useState<Law[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [query, setQuery] = useState('')
  const [drawerSite, setDrawerSite] = useState<Site | null>(null)
  const [showForm, setShowForm] = useState(false)

  useEffect(() => {
    let cancelled = false
    apiGet<Law[]>('/api/bizdev/laws/').then(d => { if (!cancelled) setLaws(d) }).catch(() => {})
    apiGet<Summary>('/api/bizdev/summary/').then(d => { if (!cancelled) setSummary(d) }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  const devSites = useMemo(() => sites.filter(s => s.lifecycle === 'dev'), [sites])
  const devMw = devSites.reduce((a, s) => a + Number(s.capacity_mw || 0), 0)
  const solar = devSites.filter(s => s.energy_type === 'solar')
  const wind = devSites.filter(s => s.energy_type === 'wind')
  const solarMw = solar.reduce((a, s) => a + Number(s.capacity_mw || 0), 0)
  const windMw = wind.reduce((a, s) => a + Number(s.capacity_mw || 0), 0)
  const devGw = devMw / 1000

  const thisMonth = new Date().toISOString().slice(0, 7).replace('-', '.')
  const monthLaws = laws.filter(l => (l.date || '').startsWith(thisMonth))
  const lawBy = (cat: string) => monthLaws.filter(l => l.category === cat).length

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return sites
    return sites.filter(s => `${s.name} ${s.location || ''} ${s.sido || ''}`.toLowerCase().includes(q))
  }, [sites, query])

  const issues = summary?.monthly_pending_issues

  return (
    <section className="pane" style={{ flex: 1, overflowY: 'auto' }}>
      <div className="section-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h2>사업개발 Dashboard</h2>
          <p>재생에너지 개발 자산 파이프라인 · 계통 · 법령 통합 현황</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input className="inp" style={{ width: 200 }} placeholder="사업지·지역 검색"
                 value={query} onChange={e => setQuery(e.target.value)} />
          <button className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 5 }}
                  onClick={() => setShowForm(true)}>
            <Plus size={15} /> 사업지 등록
          </button>
        </div>
      </div>

      {/* KPI 4장 */}
      <div className="kpi-row">
        <div className="kpi">
          <div className="k-lab"><Landmark size={15} /> 전체 파이프라인</div>
          <div className="k-val">{TOTAL_PIPELINE.sites}<span className="u">개소</span> · {TOTAL_PIPELINE.gw}<span className="u">GW</span></div>
          <div className="k-sub">개발중 {devSites.length}개소 {devGw.toFixed(1)}GW · 발굴·검토 {TOTAL_PIPELINE.sites - devSites.length}개소 {(TOTAL_PIPELINE.gw - devGw).toFixed(1)}GW</div>
        </div>
        <div className="kpi">
          <div className="k-lab"><Sun size={15} /> 개발 중 파이프라인</div>
          <div className="k-val">{devSites.length}<span className="u">개소</span> · {devGw.toFixed(2)}<span className="u">GW</span></div>
          <div className="k-sub">태양광 {solar.length}개소 {Math.round(solarMw)}MW / 풍력 {wind.length}개소 {Math.round(windMw)}MW</div>
        </div>
        <div className="kpi">
          <div className="k-lab"><AlertTriangle size={15} /> 금월 Pending 이슈</div>
          <div className="k-val">{issues?.total ?? '-'}<span className="u">건</span></div>
          <div className="k-sub">민원성 {issues?.by.complaint ?? 0} · 계통 {issues?.by.grid ?? 0} · 기타 {issues?.by.etc ?? 0}</div>
        </div>
        <div className="kpi">
          <div className="k-lab"><Scale size={15} /> 금월 주요 법령 동향</div>
          <div className="k-val">{monthLaws.length}<span className="u">건</span></div>
          <div className="k-sub">입법예고 {lawBy('입법예고')} · 시행 {lawBy('시행')} · 개정 {lawBy('개정')}</div>
        </div>
      </div>

      {/* 지도 + 우측 레일 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(260px, 1fr)', gap: 16, marginBottom: 22 }}>
        <div className="card block" style={{ display: 'flex', flexDirection: 'column', position: 'relative', minHeight: 440 }}>
          <h3>포트폴리오 지도</h3>
          <div className="h-sub" style={{ marginBottom: 10 }}>마커 클릭 → 요약 · 상세 이동 (태양광 주황 / 풍력 청록)</div>
          <SiteMap sites={filtered} onPick={setDrawerSite} />
          {drawerSite && (
            <SiteDrawer site={drawerSite} onClose={() => setDrawerSite(null)}
                        onDetail={s => { setDrawerSite(null); onSelectSite(s.id) }} />
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <GridRail sites={sites} />
          <LawRail laws={laws} />
        </div>
      </div>

      {/* 인허가 진척 파이프라인 */}
      <div className="card block">
        <h3>인허가 진척 파이프라인</h3>
        <div className="h-sub" style={{ marginBottom: 12 }}>행 클릭 → 사업지 상세 (개발/운영 사업은 각각 다른 상세 화면)</div>
        <PipelineTable sites={filtered} onSelectSite={onSelectSite} />
      </div>

      {showForm && <SiteFormModal onClose={() => setShowForm(false)} onSaved={onSitesChanged} />}
    </section>
  )
}
