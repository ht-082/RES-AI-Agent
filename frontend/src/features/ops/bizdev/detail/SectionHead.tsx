import { Pencil } from 'lucide-react'

/** 최근 수정 시각을 "최종 편집 YYYY-MM-DD" 로. 값이 없으면 표시하지 않는다. */
export function lastEdited(stamps: Array<string | undefined | null>): string {
  const valid = stamps.filter(Boolean) as string[]
  if (valid.length === 0) return ''
  const latest = valid.reduce((a, b) => (a > b ? a : b))
  const d = new Date(latest)
  if (isNaN(d.getTime())) return ''
  return `최종 편집 ${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// 섹션 카드 머리 — 제목 · (부가 배지) · 최종 편집일 · 편집 버튼
export default function SectionHead({ title, updatedAt, canEdit, onEdit, extra }: {
  title: string
  updatedAt?: string
  canEdit?: boolean          // 편집이 없는 카드(계통·조례)는 넘기지 않는다
  onEdit?: () => void
  extra?: React.ReactNode
}) {
  return (
    <div className="bz-sec-head">
      <h3>{title}</h3>
      <div className="bz-sec-actions">
        {extra}
        {updatedAt && <span className="bz-updated">{updatedAt}</span>}
        {canEdit && onEdit && (
          <button className="btn-ghost bz-edit-btn" onClick={onEdit}>
            <Pencil size={13} /> 상세내용 확인 및 편집
          </button>
        )}
      </div>
    </div>
  )
}
