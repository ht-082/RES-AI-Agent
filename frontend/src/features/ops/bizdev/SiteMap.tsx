import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { ENERGY_META, KOREA_BOUNDS, siteCoords } from './constants'
import type { Site } from './types'

const TILES = {
  voyager: {
    label: '일반',
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    options: { subdomains: 'abcd', attribution: '&copy; OpenStreetMap &copy; CARTO' },
  },
  positron: {
    label: '밝게',
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    options: { subdomains: 'abcd', attribution: '&copy; OpenStreetMap &copy; CARTO' },
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
    const map = L.map(boxRef.current, { scrollWheelZoom: true })
    map.fitBounds(L.latLngBounds(KOREA_BOUNDS))
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
    if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [50, 50], maxZoom: 9 })
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
        {/* 고정 줌이 아니라 경계 맞춤 — 지도 칸 너비가 바뀌어도 우리나라가
            잘리거나 빈 바다가 남지 않는다 */}
        <button className="bz-map-btn"
                onClick={() => mapRef.current?.fitBounds(L.latLngBounds(KOREA_BOUNDS))}>전국</button>
      </div>
    </div>
  )
}
