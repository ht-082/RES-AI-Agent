import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import FactTable from './FactTable'
import SectionHead, { lastEdited } from './SectionHead'
import SectionModal from './SectionModal'
import { ENERGY_META } from '../constants'
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

  useEffect(() => {
    if (!boxRef.current) return
    if (mapRef.current) { mapRef.current.remove(); mapRef.current = null }
    if (site.lat == null || site.lng == null) return
    const map = L.map(boxRef.current, { scrollWheelZoom: false, zoomControl: false })
      .setView([site.lat, site.lng], 13)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { attribution: 'Tiles &copy; Esri' }).addTo(map)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
      { attribution: '' }).addTo(map)
    const color = ENERGY_META[site.energy_type]?.color || '#f59e0b'
    L.marker([site.lat, site.lng], {
      icon: L.divIcon({
        className: 'bz-pin-wrap',
        html: `<div class="bz-pin" style="--pin-color:${color}"><span class="bz-pin-head"></span></div>`,
        iconSize: [26, 34], iconAnchor: [13, 30],
      }),
    }).addTo(map)
    mapRef.current = map

    // 지도 높이가 카드 높이에 따라 달라지므로 컨테이너가 바뀌면 다시 그리게 한다.
    // (Leaflet 은 컨테이너 크기를 스스로 감지하지 못해 타일이 잘린 채 남는다)
    const ro = new ResizeObserver(() => map.invalidateSize())
    ro.observe(boxRef.current)

    return () => { ro.disconnect(); map.remove(); mapRef.current = null }
  }, [site.id, site.lat, site.lng, site.energy_type])

  const updatedAt = lastEdited(facts.map(f => f.updated_at))

  return (
    <div className="card block bz-overview" id={id}>
      <SectionHead title="사업 개요" updatedAt={updatedAt} canEdit={canEdit}
                   onEdit={() => setEditing(true)} />
      <div ref={boxRef} className="bz-overview-map">
        {(site.lat == null || site.lng == null) && (
          <p className="note" style={{ padding: 20 }}>위경도 미입력 — 지도 표시 불가</p>
        )}
      </div>

      <FactTable facts={facts} canEdit={canEdit} onChanged={onChanged} />

      {editing && (
        <SectionModal title="사업 개요" onClose={() => { setEditing(false); onChanged() }}>
          <FactTable facts={facts} editable canEdit={canEdit} onChanged={onChanged} />
        </SectionModal>
      )}
    </div>
  )
}
