import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { ENERGY_META, KOREA_BOUNDS, siteCoords } from './constants'
import type { Site } from './types'

// CARTO(basemaps.cartocdn.com) 는 이제 키 없이 쓰면 타일마다 'API KEY
// REQUIRED' 워터마크를 찍는다(2026-09-22 실측 — 일반·밝게 두 장 모두).
// 키 없이 깨끗하게 나오는 것으로 바꿨다. 일반은 지명이 한글로 나오는
// OpenStreetMap 표준, 밝게는 Esri Light Gray.
const TILES = {
  voyager: {
    label: '일반',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    options: { attribution: '&copy; OpenStreetMap contributors', maxZoom: 19 },
  },
  positron: {
    label: '밝게',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    options: { attribution: 'Tiles &copy; Esri' },
  },
  satellite: {
    label: '위성',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    options: { attribution: 'Tiles &copy; Esri' },
  },
} as const

type TileKey = keyof typeof TILES

function pinHtml(site: Site, approx: boolean): string {
  const color = ENERGY_META[site.energy_type]?.color || '#f59e0b'
  const pulse = site.status === 'risk' ? '<span class="bz-pin-pulse"></span>' : ''
  return `<div class="bz-pin${approx ? ' approx' : ''}" style="--pin-color:${color}">`
    + `${pulse}<span class="bz-pin-head"></span></div>`
}

// 명령형 Leaflet 지도 — 원본 index.page.js 지도 로직 이식(타일 3종 · 핀 · 클릭 선택)
export default function SiteMap({ sites, onPick }: {
  sites: Site[]
  onPick: (site: Site) => void
}) {
  const boxRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const tileLayerRef = useRef<L.TileLayer | null>(null)
  const markersRef = useRef<L.Marker[]>([])
  const [tile, setTile] = useState<TileKey>('voyager')

  useEffect(() => {
    if (!boxRef.current || mapRef.current) return
    // zoomSnap: 0 — 기본값(1)이면 fitBounds 가 줌을 정수로 내려 버려서,
    // 401x538 칸에 남한이 173x314(세로 58%)로 작게 떠 있었다. 소수 줌을
    // 허용해야 경계가 칸에 정확히 맞는다(실측: 줌 6 → 6.776, 세로 100%).
    const map = L.map(boxRef.current, { scrollWheelZoom: true, zoomSnap: 0 })
    map.fitBounds(L.latLngBounds(KOREA_BOUNDS), { animate: false })
    mapRef.current = map
    return () => { map.remove(); mapRef.current = null }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (tileLayerRef.current) map.removeLayer(tileLayerRef.current)
    const t = TILES[tile]
    tileLayerRef.current = L.tileLayer(t.url, t.options as L.TileLayerOptions).addTo(map)
  }, [tile])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    markersRef.current.forEach(m => map.removeLayer(m))
    markersRef.current = []
    const pts: L.LatLngExpression[] = []
    sites.forEach(site => {
      const at = siteCoords(site)
      if (!at) return
      const marker = L.marker([at.lat, at.lng], {
        icon: L.divIcon({ className: 'bz-pin-wrap', html: pinHtml(site, at.approx),
                          iconSize: [26, 34], iconAnchor: [13, 30] }),
      })
        .bindTooltip(`${site.name} · ${Math.round(Number(site.capacity_mw))}MW`
                     + (at.approx ? ' · 대략 위치(시·군 중심)' : ''),
                     { direction: 'top', offset: [0, -26] })
        .on('click', () => onPick(site))
        .addTo(map)
      markersRef.current.push(marker)
      pts.push([at.lat, at.lng])
    })
    if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [50, 50], maxZoom: 9, animate: false })
  }, [sites, onPick])

  return (
    <div style={{ position: 'relative', flex: 1, minHeight: 380 }}>
      <div ref={boxRef} style={{ position: 'absolute', inset: 0, borderRadius: 10, overflow: 'hidden' }} />
      <div className="bz-map-ctrl">
        {(Object.keys(TILES) as TileKey[]).map(k => (
          <button key={k} className={`bz-map-btn ${tile === k ? 'on' : ''}`} onClick={() => setTile(k)}>
            {TILES[k].label}
          </button>
        ))}
        {/* 고정 줌이 아니라 경계 맞춤 — 지도 칸 너비가 바뀌어도 남한이
            잘리거나 빈 바다가 남지 않는다.
            animate: false — 줌 애니메이션이 끝나지 않으면 Leaflet 이
            _animatingZoom 을 켠 채로 남겨 이후 줌 호출을 전부 무시한다.
            뷰를 되돌리는 버튼이라 즉시 이동이 맞기도 하다. */}
        <button className="bz-map-btn"
                onClick={() => mapRef.current?.fitBounds(L.latLngBounds(KOREA_BOUNDS),
                                                         { animate: false })}>전국</button>
      </div>
    </div>
  )
}
