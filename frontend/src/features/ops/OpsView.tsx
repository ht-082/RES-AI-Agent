import { useState } from 'react'
import OpsMonitorTab from './OpsMonitorTab'
import BizdevTab from './bizdev/BizdevTab'
import type { AppUser } from './bizdev/types'

type OpsTab = 'monitor' | 'bizdev'

// 운영관리 뷰 — [운영 현황 | 사업개발] 탭 래퍼.
// 운영 현황은 기존 하드코딩 목업(OpsMonitorTab), 사업개발은 bizdev API 연동 대시보드.
export default function OpsView({ user }: { user: AppUser | null }) {
  const [tab, setTab] = useState<OpsTab>('bizdev')

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div className="tabs">
        <div className={`tab ${tab === 'bizdev' ? 'active' : ''}`} onClick={() => setTab('bizdev')}>
          사업개발
        </div>
        <div className={`tab ${tab === 'monitor' ? 'active' : ''}`} onClick={() => setTab('monitor')}>
          운영 현황
        </div>
      </div>
      {tab === 'monitor' ? <OpsMonitorTab /> : <BizdevTab user={user} />}
    </div>
  )
}
