import { useEffect, useMemo, useState } from 'react'
import { Landmark, Plus, Scale, Sun } from 'lucide-react'
import SiteMap from './SiteMap'
import SiteDrawer from './SiteDrawer'
import LawRail from './LawRail'
import PipelineTable from './PipelineTable'
import SiteFormModal from './SiteFormModal'
import SectionHead from './detail/SectionHead'
import { apiGet, apiSend } from './api'
import KpiValue from './KpiValue'
import { formatKRW } from './constants'
import type { AppUser, Law, Site } from './types'

interface Kpi {
  key: string
  label: string
  value: string | null
  note: string
}

// 사업개발 메인 대시보드 — 원본 index.html 이식
export default function BizdevDashboard({ sites, onSelectSite, onSitesChanged }: {
  sites: Site[]
  user: AppUser | null
  onSelectSite: (id: string) => void
  onSitesChanged: () => void
}) {
  const [laws, setLaws] = useState<Law[]>([])
  const [kpis, setKpis] = useState<Kpi[]>([])
  const [query, setQuery] = useState('')
  const [drawerSite, setDrawerSite] = useState<Site | null>(null)
  const [showForm, setShowForm] = useState(false)

  useEffect(() => {
    let cancelled = false
    apiGet<Law[]>('/api/bizdev/laws/').then(d => { if (!cancelled) setLaws(d) }).catch(() => {})
    apiGet<Kpi[]>('/api/bizdev/kpis/').then(d => { if (!cancelled) setKpis(d) }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  const mw = (list: Site[]) => list.reduce((a, s) => a + Number(s.capacity_mw || 0), 0)
  const devSites = useMemo(() => sites.filter(s => s.lifecycle === 'dev'), [sites])
  const opsSites = useMemo(() => sites.filter(s => s.lifecycle === 'ops'), [sites])
  const totalGw = mw(sites) / 1000
  const opsGw = mw(opsSites) / 1000
  const devGw = mw(devSites) / 1000

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return sites
    return sites.filter(s => `${s.name} ${s.location || ''} ${s.sido || ''}`.toLowerCase().includes(q))
  }, [sites, query])

  // 아직 자동 집계가 없는 지표 — 값이 없으면 null 로 두어 '0' 과 구분한다
  const kpi = (key: string) => {
    const row = kpis.find(k => k.key === key)
    return row?.value == null ? null : Number(row.value)
  }
  const kpiYear = new Date().getFullYear()
  const saveKpi = async (key: string, value: number | null) => {
    const row = await apiSend<Kpi>('PATCH', `/api/bizdev/kpis/${key}/`, { value })
    setKpis(prev => prev.map(k => (k.key === key ? row : k)))
  }

  return (
    <section className="pane" style={{ flex: 1, overflowY: 'auto' }}>
      <div className="section-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h2>전체 사업 파이프라인</h2>
          <p>재생에너지 자산 통합 현황 · 개발 사업은 개발 상세, 운영 사업은 운영 상세로 이동</p>
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

      {/* KPI 3장 — 1번은 사업지 목록에서 자동으로 세고, 2·3번은 자동 집계가
          붙기 전까지 눌러서 직접 넣는다(근거가 생기면 읽기 전용 계산값으로 교체). */}
      <div className="kpi-row bz-kpi-3">
        <div className="kpi">
          <div className="k-lab"><Landmark size={15} /> 전체 등록 사업</div>
          <div className="k-val">{sites.length}<span className="u">개소</span> · {totalGw.toFixed(2)}<span className="u">GW</span></div>
          <div className="k-sub">개발중 {devSites.length}개소 {devGw.toFixed(2)}GW · 운영중 {opsSites.length}개소 {opsGw.toFixed(2)}GW</div>
        </div>
        <div className="kpi">
          <div className="k-lab"><Sun size={15} /> 올해 Pipeline 확보 실적</div>
          <div className="k-val">
            <KpiValue value={kpi('pipeline_secured_mw')} unit="MW"
                      format={v => v.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                      onSaved={v => saveKpi('pipeline_secured_mw', v)} />
          </div>
          <div className="k-sub">{kpiYear}년 확보 · 직접 입력</div>
        </div>
        <div className="kpi">
          <div className="k-lab"><Scale size={15} /> 재무 실적</div>
          <div className="k-val bz-kpi-pair">
            <KpiValue value={kpi('revenue_month_krw')} unit="" format={formatKRW}
                      onSaved={v => saveKpi('revenue_month_krw', v)} />
            <span className="bz-kpi-sep">/</span>
            <KpiValue value={kpi('profit_month_krw')} unit="" format={formatKRW}
                      onSaved={v => saveKpi('profit_month_krw', v)} />
          </div>
          <div className="k-sub">당월 총 매출 / 영업이익 · 직접 입력</div>
        </div>
      </div>

      {/* 지도 + 우측 레일 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(300px, 1fr)', gap: 16, marginBottom: 22 }}>
        <div className="card block" style={{ display: 'flex', flexDirection: 'column', position: 'relative', minHeight: 440 }}>
          <SectionHead title="포트폴리오 지도" />
          <div className="h-sub" style={{ marginBottom: 10 }}>마커 클릭 → 요약 · 상세 이동 (태양광 주황 / 풍력 청록)</div>
          <SiteMap sites={filtered} onPick={setDrawerSite} />
          {drawerSite && (
            <SiteDrawer site={drawerSite} onClose={() => setDrawerSite(null)}
                        onDetail={s => { setDrawerSite(null); onSelectSite(s.id) }} />
          )}
        </div>
        {/* 우측에는 법령 동향만 — 지도와 아래 끝을 맞춘다 */}
        <div className="bz-stack" style={{ gap: 16 }}>
          <LawRail laws={laws} />
        </div>
      </div>

      {/* 사업 List */}
      <div className="card block">
        <SectionHead title="사업 List" />
        <div className="h-sub" style={{ marginBottom: 12 }}>
          행 클릭 → 개발 사업은 인허가·예산 상세로, 운영 사업은 발전 실적 상세로 이동
        </div>
        {/* 개발 중과 운영 중은 봐야 할 것이 다르다(인허가 진척 ↔ 발전 실적).
            한 표에 섞으면 진척률 칸이 운영 사업에서 늘 100%로 남아 눈만 어지럽다. */}
        {([['dev', '개발 중'], ['ops', '운영 중']] as const).map(([life, label]) => {
          const rows = filtered.filter(s => s.lifecycle === life)
          const mw = rows.reduce((a, s) => a + Number(s.capacity_mw || 0), 0)
          return (
            <div key={life} className="bz-list-group">
              <div className="bz-block-title">
                {label}
                <span className="bz-list-count">{rows.length}개소 · {Math.round(mw)}MW</span>
              </div>
              {rows.length === 0
                ? <p className="note">해당 사업이 없습니다.</p>
                : <PipelineTable sites={rows} onSelectSite={onSelectSite} />}
            </div>
          )
        })}
      </div>

      {showForm && <SiteFormModal onClose={() => setShowForm(false)} onSaved={onSitesChanged} />}
    </section>
  )
}
