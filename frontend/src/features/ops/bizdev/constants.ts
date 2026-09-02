// 사업개발 대시보드 공용 상수 — 원본 Re-project-mng 로직 이식
import type { Certainty, Site, SiteStatus, StageStatus, StageSummary } from './types'

// 인허가 상태 — 사업개요 양식 기준(완료/진행중/미착수/미대상)
export const STATUS_META: Record<StageStatus, { label: string; color: string }> = {
  done:   { label: '완료',   color: 'var(--green-accent)' },
  active: { label: '진행중', color: 'var(--brand)' },
  idle:   { label: '미착수', color: '#b8c4bd' },
  na:     { label: '미대상', color: '#cbd5e1' },
}
export const STATUS_ORDER: StageStatus[] = ['idle', 'active', 'done', 'na']

// 사업지 상태(지도 핀·배지) — 5단계 유지
export const SITE_STATUS_META: Record<SiteStatus, { label: string; color: string }> = {
  done:   { label: '완료',   color: 'var(--green-accent)' },
  active: { label: '진행중', color: 'var(--brand)' },
  wait:   { label: '대기',   color: 'var(--amber)' },
  risk:   { label: '리스크', color: 'var(--red)' },
  idle:   { label: '미착수', color: '#b8c4bd' },
}

// 확정도 — 사업개요 양식 전 항목 공통
export const CERTAINTY_META: Record<Certainty, { label: string; color: string }> = {
  confirmed:   { label: '확정',   color: 'var(--green-accent)' },
  unconfirmed: { label: '미확정', color: 'var(--amber)' },
  na:          { label: '해당없음', color: '#b8c4bd' },
}

export const CONTRACT_STATUS_META: Record<string, { label: string; color: string }> = {
  signed:  { label: '체결',      color: 'var(--green-accent)' },
  planned: { label: '체결 예정', color: 'var(--amber)' },
  none:    { label: '미체결',    color: '#b8c4bd' },
}

// 계약 유형 — 서버 CONTRACT_CATEGORY_CHOICES 와 같은 순서
export const CONTRACT_CATEGORIES: Array<[string, string]> = [
  ['land_lease', '부지 임대차'], ['dev_service', '개발용역'],
  ['asset_transfer', '자산양수도'], ['expansion_agreement', '사업확장 등 합의서'],
  ['permit_service', '개발행위 인허가 용역'], ['elec_design', '전기설계 용역'],
  ['eia_service', '환경영향평가 용역'], ['dia_service', '재해영향평가 용역'],
  ['dev_support', '사업개발지원 용역'], ['community', '지역수용성 용역'],
  ['grid_contract', '송전용전기설비이용계약'], ['epc', 'EPC'],
  ['pf_loan', 'PF 대출약정'], ['ppa_rec', 'PPA / REC 매매'],
  ['om', 'O&M (관리운영위탁)'], ['supervision', '감리 · OE'], ['etc', '기타'],
]

export const EVENT_STATUS_META: Record<string, { label: string; color: string }> = {
  ongoing: { label: '진행중', color: 'var(--brand)' },
  hold:    { label: '보류',   color: 'var(--amber)' },
  done:    { label: '완료',   color: 'var(--green-accent)' },
}
export const EVENT_STATUSES: Array<[string, string]> = [
  ['ongoing', '진행중'], ['hold', '보류'], ['done', '완료'],
]

export const EVENT_TYPES: Array<[string, string]> = [
  ['permit', '인허가'], ['complaint', '민원'], ['land', '토지'],
  ['contract', '계약'], ['finance', '금융'], ['etc', '기타'],
]

export const ENERGY_META = {
  solar: { label: '태양광', color: '#f59e0b' },
  wind:  { label: '풍력',   color: '#06b6d4' },
} as const

export const BUDGET_CATS = [
  { key: 'land',   label: '부지',   color: '#2563eb' },
  { key: 'permit', label: '인허가', color: '#059669' },
  { key: 'design', label: '설계',   color: '#d97706' },
  { key: 'legal',  label: '법무',   color: '#7c3aed' },
  { key: 'etc',    label: '기타',   color: '#64748b' },
] as const

export const ISSUE_STATUS_META = {
  open:   { label: '진행중', color: 'var(--red)' },
  prog:   { label: '대응중', color: 'var(--amber)' },
  closed: { label: '완료',   color: 'var(--green-accent)' },
} as const

export const ISSUE_TYPE_LABEL = { complaint: '민원성', grid: '계통', etc: '기타' } as const

// ── 파이프라인 7컬럼 (원본 index.page.js:219-236 이식) ──────────────
export const PIPE_COLS = [
  { label: '발전사업허가', kw: ['발전사업허가'] },
  { label: '이용계약', kw: ['이용계약'] },
  { label: '개발행위허가', kw: ['개발행위허가'] },
  { label: '환경성 검토', kw: ['환경영향', '재해영향'] },
  { label: '공사계획인가', kw: ['공사계획'] },
  { label: '사용전검사', kw: ['사용전검사'] },
  { label: '사업개시 · 준공', kw: ['사업개시신고', '개발행위준공'] },
]

export function colStatus(stages: StageSummary[], col: (typeof PIPE_COLS)[number]): StageStatus {
  const m = stages.filter(s => col.kw.some(k => (s.name || '').includes(k)))
  if (!m.length) return 'idle'
  const target = m.filter(x => x.status !== 'na')
  if (!target.length) return 'na'
  if (target.every(x => x.status === 'done')) return 'done'
  if (target.some(x => x.status === 'active')) return 'active'
  return target.some(x => x.status === 'done') ? 'active' : 'idle'
}

// ── 시·도 정규화 (원본 index.page.js:163-181 이식) ─────────────────
const SIDO_FULL: Record<string, string> = {
  충청남도: '충남', 충청북도: '충북', 전라남도: '전남', 전라북도: '전북',
  전북특별자치도: '전북', 경상남도: '경남', 경상북도: '경북',
  강원도: '강원', 강원특별자치도: '강원', 경기도: '경기',
  제주특별자치도: '제주', 제주도: '제주', 세종특별자치시: '세종',
}
const SIDO_2 = ['충남', '충북', '전남', '전북', '경남', '경북', '강원', '경기', '제주',
  '세종', '서울', '부산', '대구', '인천', '광주', '대전', '울산']
const SIGUN_SIDO: Record<string, string> = {
  서산시: '충남', 당진시: '충남', 홍성군: '충남', 청양군: '충남', 서천군: '충남',
  태안군: '충남', 예산군: '충남', 보령시: '충남',
  영암군: '전남', 신안군: '전남', 해남군: '전남', 영광군: '전남', 완도군: '전남',
  보성군: '전남', 함평군: '전남', 나주시: '전남', 고흥군: '전남', 여수시: '전남',
  고령군: '경북', 영덕군: '경북', 김천시: '경북', 상주시: '경북', 포항시: '경북',
  밀양시: '경남', 창녕군: '경남', 진주시: '경남',
  태백시: '강원', 정선군: '강원', 영월군: '강원',
  군산시: '전북', 김제시: '전북',
  제주시: '제주', 서귀포시: '제주',
}

export function sidoOf(s: Pick<Site, 'location' | 'sido'> & { address_detail?: string }): string | null {
  const tok = String(s.address_detail || s.location || s.sido || '').trim().split(/[\s·]+/)[0] || ''
  if (SIDO_FULL[tok]) return SIDO_FULL[tok]
  const two = tok.slice(0, 2)
  if (SIDO_2.includes(two) && !/[시군구]$/.test(tok)) return two
  return SIGUN_SIDO[tok] || SIGUN_SIDO[s.sido] || null
}

// ── 포맷 (원본 js/format.js 이식) ──────────────────────────────────
export function formatKRW(won: number): string {
  if (!won && won !== 0) return '-'
  if (Math.abs(won) >= 100_000_000) {
    const v = won / 100_000_000
    return `${v % 1 === 0 ? v.toFixed(0) : v.toFixed(1)}억`
  }
  if (Math.abs(won) >= 10_000) return `${Math.round(won / 10_000).toLocaleString()}만`
  return `${won.toLocaleString()}원`
}

export function formatWonExact(won: number): string {
  return `${(won ?? 0).toLocaleString()}원`
}

export function ddayLabel(deadline: string | null, fallback: string): string {
  if (!deadline) return fallback
  const diff = Math.ceil((new Date(deadline).getTime() - Date.now()) / 86_400_000)
  if (diff === 0) return 'D-DAY'
  return diff > 0 ? `D-${diff}` : `D+${-diff}`
}

/** 좁은 표에서 쓰는 짧은 날짜 표기 — 2026-04-03 → 26.04.03 */
export function shortDate(value: string | null): string {
  if (!value) return ''
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  return m ? `${m[1].slice(2)}.${m[2]}.${m[3]}` : value
}
