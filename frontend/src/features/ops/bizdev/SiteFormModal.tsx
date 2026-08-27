import { useState } from 'react'
import { apiSend } from './api'
import type { Site } from './types'

// 사업지 등록 모달 — 원본 index.page.js 등록 모달 이식.
// 저장 시 서버가 12단계 인허가 골격을 자동 생성한다.
export default function SiteFormModal({ onClose, onSaved }: {
  onClose: () => void
  onSaved: () => void
}) {
  const [f, setF] = useState({
    name: '', capacity_mw: '', approved_budget_krw: '', lat: '', lng: '',
    location: '', sido: '', facility_type: '', energy_type: 'solar',
    annual_gwh: '', cod: '', status: 'active', risk_tag: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const set = (k: string, v: string) => setF(prev => ({ ...prev, [k]: v }))

  const save = async () => {
    if (!f.name.trim()) { setError('사업지명을 입력하세요.'); return }
    const cap = parseFloat(f.capacity_mw)
    if (isNaN(cap) || cap <= 0) { setError('설비용량(MW)을 올바르게 입력하세요.'); return }
    setSaving(true); setError('')
    try {
      await apiSend<Site>('POST', '/api/bizdev/sites/', {
        name: f.name.trim(),
        capacity_mw: cap.toFixed(1),
        approved_budget_krw: parseInt(f.approved_budget_krw.replace(/[^0-9]/g, '') || '0', 10),
        lat: f.lat ? parseFloat(f.lat) : null,
        lng: f.lng ? parseFloat(f.lng) : null,
        location: f.location.trim(),
        sido: f.sido.trim(),
        facility_type: f.facility_type.trim(),
        energy_type: f.energy_type,
        annual_gwh: f.annual_gwh ? parseFloat(f.annual_gwh).toFixed(1) : null,
        cod: f.cod.trim(),
        status: f.status,
        risk_tag: f.risk_tag.trim(),
        risk_level: f.risk_tag.trim() ? 'md' : '',
        lifecycle: 'dev',
      })
      onSaved()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : '저장에 실패했습니다.')
    } finally {
      setSaving(false)
    }
  }

  const fld = (label: string, key: keyof typeof f, placeholder = '', type = 'text') => (
    <label className="fld" style={{ fontSize: 12 }}>
      <span style={{ display: 'block', marginBottom: 4, color: 'var(--ink-soft)', fontWeight: 600 }}>{label}</span>
      <input className="inp" type={type} value={f[key]} placeholder={placeholder}
             onChange={e => set(key, e.target.value)} />
    </label>
  )

  return (
    <div className="bz-modal-back" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="bz-modal">
        <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 14 }}>사업지 등록</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {fld('사업지명 *', 'name', '예: 홍성태양광')}
          {fld('설비용량 (MW) *', 'capacity_mw', '100', 'number')}
          {fld('승인예산 (원)', 'approved_budget_krw', '1860000000')}
          <label className="fld" style={{ fontSize: 12 }}>
            <span style={{ display: 'block', marginBottom: 4, color: 'var(--ink-soft)', fontWeight: 600 }}>에너지원</span>
            <select className="inp" value={f.energy_type} onChange={e => set('energy_type', e.target.value)}>
              <option value="solar">태양광</option>
              <option value="wind">풍력</option>
            </select>
          </label>
          {fld('소재지', 'location', '충남 홍성군')}
          {fld('지자체(시·군)', 'sido', '홍성군')}
          {fld('설비유형', 'facility_type', '육상태양광')}
          {fld('연간발전량 (GWh)', 'annual_gwh', '135', 'number')}
          {fld('위도', 'lat', '36.68', 'number')}
          {fld('경도', 'lng', '126.55', 'number')}
          {fld('목표 COD', 'cod', "'27.Q4")}
          {fld('리스크 태그', 'risk_tag', '계통대기')}
        </div>
        {error && <p className="note" style={{ color: 'var(--red)', marginTop: 10 }}>{error}</p>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
          <button className="btn-ghost" onClick={onClose}>취소</button>
          <button className="btn-primary" onClick={save} disabled={saving}>
            {saving ? '저장 중...' : '등록 (12단계 자동 생성)'}
          </button>
        </div>
      </div>
    </div>
  )
}
