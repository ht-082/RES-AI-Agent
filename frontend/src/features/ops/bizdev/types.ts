// 사업개발 대시보드 타입 — /api/bizdev/* 응답 형태
export interface StageSummary {
  id: string
  stage_no: number
  name: string
  status: StageStatus
  progress_pct: number
  tier: 'major' | 'minor'
}

export type StageStatus = 'done' | 'active' | 'wait' | 'risk' | 'idle'

export interface Site {
  id: string
  slug: string
  name: string
  capacity_mw: string          // DRF Decimal → 문자열
  location: string
  sido: string
  facility_type: string
  status: StageStatus
  risk_tag: string
  risk_level: '' | 'hi' | 'md'
  pm: string | null
  pm_name: string
  target_ntp: string
  approved_budget_krw: number
  lat: number | null
  lng: number | null
  energy_type: 'solar' | 'wind'
  lifecycle: 'dev' | 'ops'
  annual_gwh: string | null
  cod: string
  created_at: string
  stages: StageSummary[]
  overall_pct: number
  can_edit: boolean
  address_detail?: string      // 상세 응답 + 편집 권한자에게만
}

export interface PermitDocument {
  id: string
  stage: string
  version: number
  file_name: string
  file_size: number | null
  is_current: boolean
  note: string
  uploaded_by: string | null
  uploaded_at: string
}

export interface PermitStage {
  id: string
  site: string
  stage_no: number
  name: string
  agency: string
  tier: 'major' | 'minor'
  status: StageStatus
  progress_pct: number
  received_date: string | null
  deadline: string | null
  detail: string
  dday_label: string
  doc_label: string
  documents: PermitDocument[]
}

export interface BudgetEntry {
  id: string
  site: string
  category: 'land' | 'permit' | 'design' | 'legal' | 'etc'
  amount_krw: number
  exec_date: string
  memo: string
  receipt_name: string
  has_receipt: boolean
  created_by: string | null
  created_at: string
}

export interface BudgetSummary {
  by_category: Record<string, number>
  total: number
  approved: number
  exec_pct: number
}

export interface CommunityIssue {
  id: string
  site: string
  issue_date: string
  title: string
  status: 'open' | 'prog' | 'closed'
  issue_type: 'complaint' | 'grid' | 'etc'
  description: string
  created_at: string
}

export interface SiteDetailPayload {
  site: Site
  stages: PermitStage[]
  budget_entries: BudgetEntry[]
  budget_summary: BudgetSummary
  issues: CommunityIssue[]
}

export interface GridRegion {
  sido: string
  available_mw: number
  sat_pct: number
  n_subst: number
  n_dl: number
  updated_at: string | null
}

export interface GridSubstation {
  name: string
  sido: string
  capacity_used_pct: number
  available_mw: number
  contract_status: '포화' | '주의' | '여유'
}

export interface Law {
  id: string
  law_name: string
  short_name: string
  law_type: string
  category: string
  title: string
  date: string
  ministry: string
  summary: string
  source_url: string
  categories: string[]
}

export interface AppUser {
  id: string
  email: string
  name: string
  role: 'admin' | 'member'
}
