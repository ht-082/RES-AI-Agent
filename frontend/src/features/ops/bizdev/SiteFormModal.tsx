import { useState } from 'react'
import { apiSend } from './api'
import type { Site } from './types'

// 사업지 등록 · 정보 수정 모달.
// site 를 주면 수정(PATCH), 없으면 신규 등록(POST — 서버가 12단계를 자동 생성).
export default function SiteFormModal({ site, onClose, onSaved }: {
  site?: Site
  onClose: () => void
  onSaved: () => void
}) {
  const editing = !!site
  const [f, setF] = useState({
    name: site?.name ?? '',
    capacity_mw: site ? String(Number(site.capacity_mw)) : '',
    approved_budget_krw: site ? String(site.approved_budget_krw ?? 0) : '',
    lat: site?.lat != null ? String(site.lat) : '',
    lng: site?.lng != null ? String(site.lng) : '',
    location: site?.location ?? '',
    sido: site?.sido ?? '',
    facility_type: site?.facility_type ?? '',
    energy_type: site?.energy_type ?? 'solar',
    lifecycle: site?.lifecycle ?? 'dev',
    status: site?.status ?? 'active',
    annual_gwh: site?.annual_gwh != null ? String(Number(site.annual_gwh)) : '',
    cod: site?.cod ?? '',
    target_ntp: site?.target_ntp ?? '',
    risk_tag: site?.risk_tag ?? '',
    risk_level: site?.risk_level || 'md',
    address_detail: site?.address_detail ?? '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const set = (k: keyof typeof f, v: string) => setF(prev => ({ ...prev, [k]: v }))

  const save = async () => {
    if (!f.name.trim()) { setError('사업지명을 입력하세요.'); return }
    const cap = parseFloat(f.capacity_mw)
    if (isNaN(cap) || cap <= 0) { setError('설비용량(MW)을 올바르게 입력하세요.'); return }
    setSaving(true); setError('')

    const payload = {
      name: f.name.trim(),
      capacity_mw: cap.toFixed(1),
      approved_budget_krw: parseInt(f.approved_budget_krw.replace(/[^0-9]/g, '') || '0', 10),
      lat: f.lat ? parseFloat(f.lat) : null,
      lng: f.lng ? parseFloat(f.lng) : null,
      location: f.location.trim(),
      sido: f.sido.trim(),
      facility_type: f.facility_type.trim(),
      energy_type: f.energy_type,
      lifecycle: f.lifecycle,
      status: f.status,
      annual_gwh: f.annual_gwh ? parseFloat(f.annual_gwh).toFixed(1) : null,
      cod: f.cod.trim(),
      target_ntp: f.target_ntp.trim(),
      risk_tag: f.risk_tag.trim(),
      // 리스크 태그가 없으면 수준도 비운다(배지를 띄우지 않기 위해)
      risk_level: f.risk_tag.trim() ? f.risk_level : '',
      address_detail: f.address_detail.trim(),
    }

    try {
      if (editing) {
        await apiSend<Site>('PATCH', `/api/bizdev/sites/${site!.id}/`, payload)
      } else {
        await apiSend<Site>('POST', '/api/bizdev/sites/', payload)
      }
      onSaved()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : '저장에 실패했습니다.')
    } finally {
      setSaving(false)
    }
  }

  const label = (text: string) => (
    <span style={{ display: 'block', marginBottom: 4, color: 'var(--ink-soft)', fontWeight: 600 }}>{text}</span>
  )
  const fld = (text: string, key: keyof typeof f, placeholder = '', type = 'text') => (
    <label className="fld" style={{ fontSize: 12 }}>
      {label(text)}
      <input className="inp" type={type} value={f[key]} placeholder={placeholder}
             onChange={e => set(key, e.target.value)} />
    </label>
  )
  const sel = (text: string, key: keyof typeof f, options: Array<[string, string]>) => (
    <label className="fld" style={{ fontSize: 12 }}>
      {label(text)}
      <select className="inp" value={f[key]} onChange={e => set(key, e.target.value)}>
        {options.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
      </select>
    </label>
  )

  return (
    <div className="bz-modal-back" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="bz-modal">
        <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>
          {editing ? '사업 정보 수정' : '사업지 등록'}
        </h3>
        <p className="h-sub" style={{ marginBottom: 14 }}>
          {editing
            ? '개발중 ↔ 운영중을 바꾸면 상세 화면도 그에 맞게 전환됩니다.'
            : '이름과 설비용량만 필수입니다. 저장하면 인허가 12단계가 자동 생성됩니다.'}
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {fld('사업지명 *', 'name', '예: 홍성태양광')}
          {fld('설비용량 (MW) *', 'capacity_mw', '100', 'number')}
          {sel('사업 단계', 'lifecycle', [['dev', '개발중'], ['ops', '운영중']])}
          {sel('에너지원', 'energy_type', [['solar', '태양광'], ['wind', '풍력']])}
          {sel('진행 상태', 'status', [
            ['active', '진행중'], ['wait', '대기'], ['risk', '리스크'],
            ['done', '완료'], ['idle', '미착수'],
          ])}
          {fld('승인예산 (원)', 'approved_budget_krw', '1860000000')}
          {fld('소재지', 'location', '충남 홍성군')}
          {fld('지자체(시·군)', 'sido', '홍성군')}
          {fld('설비유형', 'facility_type', '육상태양광')}
          {fld('연간발전량 (GWh)', 'annual_gwh', '135', 'number')}
          {fld('위도', 'lat', '36.68', 'number')}
          {fld('경도', 'lng', '126.55', 'number')}
          {fld('목표 COD', 'cod', "'27.Q4")}
          {fld('목표 NTP', 'target_ntp', "'27.Q2")}
          {fld('리스크 태그', 'risk_tag', '계통대기')}
          {sel('리스크 수준', 'risk_level', [['md', '중간'], ['hi', '높음']])}
          <label className="fld" style={{ fontSize: 12, gridColumn: '1 / -1' }}>
            {label('상세 주소 (내부용 · 화면에 노출되지 않음)')}
            <input className="inp" value={f.address_detail} placeholder="충남 홍성군 갈산면 기산리 780"
                   onChange={e => set('address_detail', e.target.value)} />
          </label>
        </div>

        {error && <p className="note" style={{ color: 'var(--red)', marginTop: 10 }}>{error}</p>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
          <button className="btn-ghost" onClick={onClose}>취소</button>
          <button className="btn-primary" onClick={save} disabled={saving}>
            {saving ? '저장 중...' : editing ? '저장' : '등록 (12단계 자동 생성)'}
          </button>
        </div>
      </div>
    </div>
  )
}
