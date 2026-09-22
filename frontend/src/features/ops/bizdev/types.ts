// 사업개발 대시보드 타입 — /api/bizdev/* 응답 형태
export interface StageSummary {
  id: string
  stage_no: number
  name: string
  status: StageStatus
  tier: 'major' | 'minor'
}

export interface FactInputSpec {
  input: 'text' | 'select' | 'number' | 'date' | 'address' | 'substation'
       | 'grid_distance' | 'aliases' | 'shareholders' | 'derived' | 'computed'
  options?: string[]
  unit?: string
  display?: string
  parent?: string
}

export interface SiteFact {
  id: string
  site: string
  section: string
  key: string
  label: string
  value: string
  certainty: Certainty
  source: string
  note: string
  sort_order: number
  input_spec: FactInputSpec
  updated_at: string
}

export interface Contract {
  id: string
  site: string
  category: string
  category_label: string
  counterparty: string
  amount: string
  summary: string
  certainty: Certainty
  status: 'signed' | 'planned' | 'none'
  status_label: string
  note: string
  sort_order: number
  created_at: string
  updated_at: string
}

export interface SiteEvent {
  id: string
  site: string
  event_date: string | null
  is_ongoing: boolean
  event_type: string
  type_label: string
  status: 'ongoing' | 'hold' | 'done'
  status_label: string
  summary: string
  certainty: Certainty
  created_at: string
  updated_at: string
}

export interface FactSection {
  key: string
  label: string
}

// 사업지 상태(지도 핀) — 5단계 유지
export type SiteStatus = 'done' | 'active' | 'wait' | 'risk' | 'idle'
// 인허가 상태 — 사업개요 양식 기준(완료/진행중/미착수/미대상)
export type StageStatus = 'done' | 'active' | 'idle' | 'na'
export type Certainty = 'confirmed' | 'unconfirmed' | 'na'

export interface Site {
  id: string
  slug: string
  name: string
  capacity_mw: string          // DRF Decimal → 문자열
  location: string
  sido: string
  facility_type: string
  status: SiteStatus
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
  category: 'statutory' | 'individual'
  status: StageStatus
  content: string
  content_fields: string[]
  certainty: Certainty
  remark: string
  received_date: string | null
  deadline: string | null
  detail: string
  dday_label: string
  doc_label: string
  documents: PermitDocument[]
  updated_at: string
}

export type BudgetCategory = 'land' | 'permit' | 'design' | 'legal' | 'etc'

export interface BudgetApproval {
  id: string
  site: string
  category: BudgetCategory
  category_label: string
  amount_krw: number
  approved_date: string | null
  memo: string
  created_at: string
  updated_at: string
}

export interface BudgetEntry {
  id: string
  site: string
  category: BudgetCategory
  category_label: string
  amount_krw: number
  exec_date: string
  payee: string
  memo: string
  receipt_name: string
  has_receipt: boolean
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface BudgetSummary {
  by_category: Record<string, number>
  approved_by_category: Record<string, number>
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

export interface OpsDaily {
  id: string
  site: string
  date: string
  generation_mwh: string | null
  pr_pct: string | null
  revenue_krw: number | null
  note: string
  updated_at: string
}

export interface OpsPlanItem {
  id: string
  site: string
  month: string
  title: string
  cycle: string
  owner: string
  status: 'planned' | 'doing' | 'done' | 'skip'
  status_label: string
  done_date: string | null
  note: string
  updated_at: string
}

export interface DefectItem {
  id: string
  site: string
  found_date: string | null
  part: string
  summary: string
  status: 'open' | 'doing' | 'done' | 'hold'
  status_label: string
  fixed_date: string | null
  counterparty: string
  note: string
  updated_at: string
}

export interface SiteDoc {
  id: string
  site: string
  category: 'ops' | 'corp' | 'permit' | 'fin'
  category_label: string
  title: string
  doc_date: string | null
  file_name: string
  file_size: number | null
  has_file: boolean
  note: string
  created_at: string
  updated_at: string
}

export interface SiteDetailPayload {
  site: Site
  sections: FactSection[]
  facts: SiteFact[]
  contracts: Contract[]
  events: SiteEvent[]
  stages: PermitStage[]
  budget_entries: BudgetEntry[]
  budget_approvals: BudgetApproval[]
  budget_summary: BudgetSummary
  issues: CommunityIssue[]
  ops_daily: OpsDaily[]
  ops_plans: OpsPlanItem[]
  defects: DefectItem[]
  site_documents: SiteDoc[]
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
  family: string          // 시행령·시행규칙까지 묶은 이름 ('농지법')
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

/** 지켜보는 법령 — 표에 올릴 법을 담당자가 고른 목록 */
export interface WatchedLaw {
  id: string
  family: string
  law_name: string
  ministry: string
  sort_order: number
  created_at: string
}

/** 법령 검색 결과 한 줄 — 시행령·시행규칙까지 묶은 단위 */
export interface LawSearchItem {
  family: string
  law_name: string
  ministry: string
  count: number          // 묶음에 딸린 법령 수 (법률 + 시행령 + 시행규칙)
  latest: string         // 가장 최근 시행일
}

export interface LawSearchResponse {
  source: 'live' | 'snapshot'   // 법제처 실시간인지, 키가 없어 스냅샷인지
  reason?: string
  results: LawSearchItem[]
}

export interface AppUser {
  id: string
  email: string
  name: string
  role: 'admin' | 'member'
}
