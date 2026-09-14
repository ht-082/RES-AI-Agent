import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import FactTable from './FactTable'
import SectionHead, { lastEdited } from './SectionHead'
import SectionModal from './SectionModal'
import { ENERGY_META, siteCoords } from '../constants'
import { apiSend } from '../api'
import { MapPin } from 'lucide-react'
import type { Site, SiteFact } from '../types'

// 사업 개요 — 양식 §1(사업 기본 정보) + 부지 위성 지도를 한 카드로 합쳤다.
// 반폭 배치라 표는 compact(근거·비고를 내용 밑 작은 줄로) 형태를 쓴다.
export default function OverviewSection({ site, facts, canEdit, onChanged, id }: {
  site: Site
  facts: SiteFact[]
  canEdit: boolean
  onChanged: () => void
  id?: string
}) {
  const boxRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const [editing, setEditing] = useState(false)
  // 대표 필지 좌표를 지도에서 직접 찍는 모드. 주소→좌표 변환(지오코딩)은 외부
  // API 키가 필요해, 키 없이도 정확한 지점을 남길 수 있게 해 둔다.
  const [picking, setPicking] = useState(false)
  const pickingRef = useRef(false)
  pickingRef.current = picking

  const at = siteCoords(site)

  const savePoint = async (lat: number, lng: number) => {
    await apiSend('PATCH', `/api/bizdev/sites/${site.id}/`,
                  { lat: Number(lat.toFixed(6)), lng: Number(lng.toFixed(6)) })
    setPicking(false)
    onChanged()
  }

  useEffect(() => {
    if (!boxRef.current) return
    if (mapRef.current) { mapRef.current.remove(); mapRef.current = null }
    if (!at) return
    const map = L.map(boxRef.current, { scrollWheelZoom: false, zoomControl: false })
      .setView([at.lat, at.lng], at.approx ? 11 : 15)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { attribution: 'Tiles &copy; Esri' }).addTo(map)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
      { attribution: '' }).addTo(map)
    const color = ENERGY_META[site.energy_type]?.color || '#f59e0b'
    L.marker([at.lat, at.lng], {
      icon: L.divIcon({
        className: 'bz-pin-wrap',
        html: `<div class="bz-pin${at.approx ? ' approx' : ''}" style="--pin-color:${color}">`
              + '<span class="bz-pin-head"></span></div>',
        iconSize: [26, 34], iconAnchor: [13, 30],
      }),
    }).addTo(map)
    map.on('click', e => { if (pickingRef.current) void savePoint(e.latlng.lat, e.latlng.lng) })
    mapRef.current = map

    // 지도 높이가 카드 높이에 따라 달라지므로 컨테이너가 바뀌면 다시 그리게 한다.
    // (Leaflet 은 컨테이너 크기를 스스로 감지하지 못해 타일이 잘린 채 남는다)
    const ro = new ResizeObserver(() => map.invalidateSize())
    ro.observe(boxRef.current)

    return () => { ro.disconnect(); map.remove(); mapRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [site.id, site.lat, site.lng, site.sido, site.energy_type])

  const updatedAt = lastEdited(facts.map(f => f.updated_at))

  return (
    <div className="card block bz-overview" id={id}>
      <SectionHead title="사업 개요" updatedAt={updatedAt} canEdit={canEdit}
                   onEdit={() => setEditing(true)} />
      <div ref={boxRef} className={`bz-overview-map${picking ? ' picking' : ''}`}>
        {!at && (
          <p className="note" style={{ padding: 20 }}>
            좌표도 시·군도 없어 지도를 그릴 수 없습니다 — 위치(대표 필지)를 먼저 채워 주세요.
          </p>
        )}
      </div>
      {at && (
        <div className="bz-map-foot">
          <span className="bz-map-note">
            {at.approx
              ? `대략 위치(${site.sido} 중심) — 대표 필지 좌표 미지정`
              : `대표 필지 ${at.lat.toFixed(5)}, ${at.lng.toFixed(5)}`}
          </span>
          {canEdit && (
            <button className="btn-ghost bz-edit-btn" onClick={() => setPicking(v => !v)}>
              <MapPin size={13} /> {picking ? '지정 취소' : at.approx ? '위치 지정' : '위치 변경'}
            </button>
          )}
        </div>
      )}
      {picking && (
        <p className="note bz-map-hint">지도를 눌러 대표 필지 위치를 찍어 주세요.</p>
      )}

      <FactTable facts={facts} canEdit={canEdit} onChanged={onChanged} />

      {editing && (
        <SectionModal title="사업 개요" onClose={() => { setEditing(false); onChanged() }}>
          <FactTable facts={facts} editable canEdit={canEdit} onChanged={onChanged} />
        </SectionModal>
      )}
    </div>
  )
}
