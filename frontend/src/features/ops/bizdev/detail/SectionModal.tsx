import { useEffect } from 'react'
import { X } from 'lucide-react'

// 섹션 편집 팝업 껍데기.
// 본문의 각 칸은 고칠 때마다 저장되므로(자동 저장) 닫기만 하면 된다.
export default function SectionModal({ title, hint, onClose, children }: {
  title: string
  hint?: string
  onClose: () => void
  children: React.ReactNode
}) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', esc)
    return () => document.removeEventListener('keydown', esc)
  }, [onClose])

  return (
    <div className="bz-modal-back" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="bz-modal bz-modal-wide">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div>
            <h3 style={{ fontSize: 15, fontWeight: 700 }}>{title}</h3>
            <div className="h-sub">{hint || '고친 내용은 자동 저장됩니다'}</div>
          </div>
          <button className="btn-ghost" style={{ padding: 4 }} onClick={onClose} aria-label="닫기">
            <X size={16} />
          </button>
        </div>
        <div style={{ marginTop: 12 }}>{children}</div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
          <button className="btn-primary" onClick={onClose}>완료</button>
        </div>
      </div>
    </div>
  )
}
