import { useCallback, useEffect, useMemo, useState } from 'react'
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
import type { AppUser, Law, LawCatalogItem, Site, WatchedLaw } from './types'

interface Kpi {
  key: string
  label: string
  value: string | null
  note: string
}

// 사업개발 메인 대시보드 — 원본 index.html 이식
export default function BizdevDashboard({ sites, onSelectSite, onSitesChanged, onOpenChat }: {
  sites: Site[]
  user: AppUser | null
  onSelectSite: (id: string) => void
  onSitesChanged: () => void
  onOpenChat?: (conversationId: string) => void   // 법령 AI 제언 → 챗봇으로
}) {
  const [laws, setLaws] = useState<Law[]>([])
  const [watchedLaws, setWatchedLaws] = useState<WatchedLaw[]>([])
  const [lawCatalog, setLawCatalog] = useState<LawCatalogItem[]>([])
  const [kpis, setKpis] = useState<Kpi[]>([])
  const [advising, setAdvising] = useState<string | null>(null)
  const [advisingName, setAdvisingName] = useState('')
  const [advisingSec, setAdvisingSec] = useState(0)
  const [query, setQuery] = useState('')
  const [drawerSite, setDrawerSite] = useState<Site | null>(null)
  const [showForm, setShowForm] = useState(false)

  // 관심 법령이 바뀌면 동향 표도 같이 다시 받아야 한다 — 서버가 그 목록으로
  // 걸러 주기 때문에 둘을 따로 갱신하면 화면이 어긋난다.
  const loadLaws = useCallback(async () => {
    const [rows, picked] = await Promise.all([
      apiGet<Law[]>('/api/bizdev/laws/'),
      apiGet<WatchedLaw[]>('/api/bizdev/watched-laws/'),
    ])
    setLaws(rows)
    setWatchedLaws(picked)
  }, [])

  useEffect(() => {
    let cancelled = false
    loadLaws().catch(() => {})
    apiGet<LawCatalogItem[]>('/api/bizdev/laws/catalog/')
      .then(d => { if (!cancelled) setLawCatalog(d) }).catch(() => {})
    apiGet<Kpi[]>('/api/bizdev/kpis/').then(d => { if (!cancelled) setKpis(d) }).catch(() => {})
    return () => { cancelled = true }
  }, [loadLaws])

  // 제언은 사내 자료를 뒤지고 답을 쓰는 데 1분 가까이 걸린다. 멈춘 것처럼
  // 보이지 않게 경과 시간을 센다.
  useEffect(() => {
    if (!advising) return
    setAdvisingSec(0)
    const t = window.setInterval(() => setAdvisingSec(v => v + 1), 1000)
    return () => window.clearInterval(t)
  }, [advising])

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

  // AI 제언 — 질문은 서버가 만들고, 보내는 것은 챗봇 API 로.
  // 답변까지 받은 뒤에 화면을 옮긴다. 먼저 옮기면 챗봇이 아직 비어 있는 대화를
  // 읽고 끝나 버린다(같은 대화 id 라 다시 읽지도 않는다).
  // 법령마다 새 대화를 연다 — 사람마다 후속 질문을 따로 이어갈 수 있도록.
  const askAdvice = async (law: Law) => {
    if (!onOpenChat) return
    setAdvising(law.id)
    setAdvisingName(law.short_name || law.law_name)
    try {
      const { title, prompt } = await apiGet<{ title: string; prompt: string }>(
        `/api/bizdev/laws/${law.id}/advice-prompt/`)
      const conv = await apiSend<{ id: string }>('POST', '/api/conversations/',
                                                 { title, use_internal_docs: true })
      await apiSend('POST', `/api/conversations/${conv.id}/messages/`, { content: prompt })
      onOpenChat(conv.id)
    } catch (e) {
      alert(e instanceof Error ? e.message : '챗봇으로 넘기지 못했습니다.')
    } finally {
      setAdvising(null)
    }
  }

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
          <LawRail laws={laws} watched={watchedLaws} catalog={lawCatalog}
                   onAdvise={askAdvice} busyId={advising}
                   onWatchedChanged={() => { void loadLaws() }} />
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

      {advising && (
        <div className="bz-advice-toast">
          <span className="bz-spinner" />
          <div>
            <p className="bz-advice-loading-title">AI 제언을 만들고 있습니다</p>
            <p className="bz-advice-loading-sub">
              {advisingName} · 사내 자료를 찾아 답을 씁니다 · {advisingSec}초 경과
            </p>
            <p className="bz-advice-loading-sub">다 되면 대화 화면으로 넘어갑니다 (보통 30초~1분)</p>
          </div>
        </div>
      )}

      {showForm && <SiteFormModal onClose={() => setShowForm(false)} onSaved={onSitesChanged} />}
    </section>
  )
}
