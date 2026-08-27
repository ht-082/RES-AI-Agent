// 사업개발 대시보드 공용 상수 — 원본 Re-project-mng 로직 이식
import type { Site, StageStatus, StageSummary } from './types'

// 상태 → 표시 메타 (색은 RES 그린 테마 변수)
export const STATUS_META: Record<StageStatus, { label: string; color: string }> = {
  done:   { label: '완료',   color: 'var(--green-accent)' },
  active: { label: '진행중', color: 'var(--brand)' },
  wait:   { label: '대기',   color: 'var(--amber)' },
  risk:   { label: '리스크', color: 'var(--red)' },
  idle:   { label: '미착수', color: '#b8c4bd' },
}

// 상태 순환(원본 project.page.js:411)과 status↔progress 동기화(:412)
export const STATUS_ORDER: StageStatus[] = ['idle', 'wait', 'active', 'risk', 'done']
export const STATUS_PROG: Record<StageStatus, number> = {
  done: 100, active: 60, risk: 45, wait: 30, idle: 0,
}

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

// 전체 파이프라인 KPI 상수 (원본 index.page.js:24 — 발굴·검토 포함 가정치)
export const TOTAL_PIPELINE = { sites: 32, gw: 5 }

// ── 파이프라인 7컬럼 (원본 index.page.js:219-236 이식) ──────────────
export const PIPE_COLS = [
  { label: '발전사업\n허가', kw: ['발전사업허가'] },
  { label: '이용계약', kw: ['이용계약'] },
  { label: '환경성\n검토', kw: ['환경영향', '재해영향'] },
  { label: '본단지\n개발허가', kw: ['개발행위'] },
  { label: '선로\n개발허가', kw: ['도로점용'] },
  { label: '공사계획\n인가', kw: ['공사계획'] },
  { label: '착공', kw: [] as string[] },
]

export function colStatus(stages: StageSummary[], col: (typeof PIPE_COLS)[number]): StageStatus {
  if (col.label === '착공') {
    const g = stages.find(s => /공사계획/.test(s.name || ''))
    return g && g.status === 'done' ? 'done' : 'idle'
  }
  const m = stages.filter(s => col.kw.some(k => (s.name || '').includes(k)))
  if (!m.length) return 'idle'
  if (m.every(x => x.status === 'done')) return 'done'
  for (const st of ['risk', 'active', 'wait'] as StageStatus[]) {
    if (m.some(x => x.status === st)) return st
  }
  return m.some(x => x.status === 'done') ? 'active' : 'idle'
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
