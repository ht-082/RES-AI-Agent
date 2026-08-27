import BizdevTab from './bizdev/BizdevTab'
import type { AppUser } from './bizdev/types'

// 사업 관리 뷰 — 전체 사업 파이프라인이 본체다.
// 파이프라인/지도에서 사업을 고르면 lifecycle 에 따라 상세가 갈린다:
//   dev → 개발 상세(인허가·예산) · ops → 운영 상세(발전 실적)
// (기존 운영관리 하드코딩 목업은 폐기. 운영 PJT 전용 대시보드는 추후 별도 지시)
export default function OpsView({ user }: { user: AppUser | null }) {
  return <BizdevTab user={user} />
}
