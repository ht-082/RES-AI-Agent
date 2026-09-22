import { useEffect, useRef, useState } from 'react'
import { ExternalLink, Plus, Search, Sparkles, X } from 'lucide-react'
import SectionHead from './detail/SectionHead'
import SectionModal from './detail/SectionModal'
import { apiGet, apiSend } from './api'
import type {
  KeywordPreviewResponse, Law, LawSearchItem, LawSearchResponse, WatchedLaw,
} from './types'

// 전체 영향 법령 동향 — 지켜보는 대상을 위에 띄우고, 거기에 걸리는 개정만
// 아래 표에 올린다. 담는 방법은 두 가지다.
//   법령명 — 그 법과 시행령 · 시행규칙 ('농지법' → 3건)
//   키워드 — 본문에 그 말이 든 법. 새로 생긴 법이나 엉뚱한 법에 끼어든
//            재생에너지 조문은 법령명만 지켜봐서는 영영 못 본다.
// 표에서는 둘을 구분하지 않는다 — 읽는 사람에게는 '걸린 개정' 일 뿐이다.
// 법령명은 법제처 원문으로 연결한다(사내 법령 상세 화면은 2차).
// 'AI 제언'은 정해진 질문을 사내 챗봇에 넣고 그 화면으로 넘긴다.
const CAT_COLOR: Record<string, string> = {
  입법예고: 'var(--amber)',
  개정: 'var(--brand)',
  시행: 'var(--green-accent)',
  기타: 'var(--ink-faint)',
}

type Mode = 'law' | 'keyword'

export default function LawRail({ laws, watched, onAdvise, busyId, onWatchedChanged }: {
  laws: Law[]
  watched: WatchedLaw[]
  onAdvise: (law: Law) => void
  busyId?: string | null
  onWatchedChanged: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [mode, setMode] = useState<Mode>('law')
  const [busyTerm, setBusyTerm] = useState('')
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [found, setFound] = useState<LawSearchResponse | KeywordPreviewResponse | null>(null)
  const [searching, setSearching] = useState(false)
  const seq = useRef(0)

  const lawItems = watched.filter(w => w.kind === 'law')
  const kwItems = watched.filter(w => w.kind === 'keyword')
  const watchedOf = (kind: Mode, term: string) =>
    watched.find(w => w.kind === kind && w.term === term)

  // 법제처를 부르는 검색이라 글자마다 두드리지 않는다. 응답이 뒤바뀌어 도착해도
  // 마지막 입력의 결과만 남도록 순번을 붙인다.
  useEffect(() => {
    if (!editing) return
    const q = query.trim()
    if (q.length < 2) { setFound(null); setSearching(false); return }
    setSearching(true)
    const mine = ++seq.current
    const t = window.setTimeout(() => {
      apiGet<LawSearchResponse | KeywordPreviewResponse>(
        `/api/bizdev/laws/search/?mode=${mode}&q=${encodeURIComponent(q)}`)
        .then(d => { if (seq.current === mine) { setFound(d); setSearching(false) } })
        .catch(() => { if (seq.current === mine) { setFound(null); setSearching(false) } })
    }, 350)
    return () => window.clearTimeout(t)
  }, [query, mode, editing])

  const add = async (kind: Mode, term: string) => {
    setBusyTerm(term); setError('')
    try {
      await apiSend('POST', '/api/bizdev/watched-laws/', { kind, term })
      onWatchedChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : '담지 못했습니다.')
    } finally { setBusyTerm('') }
  }
  const remove = async (row: WatchedLaw) => {
    setBusyTerm(row.term); setError('')
    try {
      await apiSend('DELETE', `/api/bizdev/watched-laws/${row.id}/`)
      onWatchedChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : '빼지 못했습니다.')
    } finally { setBusyTerm('') }
  }
  const toggle = (kind: Mode, term: string) => {
    const row = watchedOf(kind, term)
    return row ? remove(row) : add(kind, term)
  }

  // 상단 요약 — 무엇을 지켜보는지 표에 들어가기 전에 알 수 있어야 한다
  const pillRow = (label: string, items: WatchedLaw[], deletable: boolean) => (
    <div className="bz-law-pillrow">
      <span className="bz-law-pilllabel">{label}</span>
      {items.length === 0 ? (
        <span className="bz-muted bz-law-pillnone">없음</span>
      ) : items.map(w => (
        <span key={w.id}
              className={`bz-law-pill${w.kind === 'keyword' ? ' kw' : ''}${deletable ? ' bz-law-pill-del' : ''}`}
              title={w.kind === 'law' ? w.law_name : `본문에 이 말이 든 법령: ${w.term}`}>
          {w.term}
          {deletable && (
            <button disabled={busyTerm === w.term} onClick={() => remove(w)}
                    aria-label={`${w.term} 빼기`}><X size={11} /></button>
          )}
        </span>
      ))}
    </div>
  )

  const kwPreview = found && found.mode === 'keyword' ? found.results : []
  const lawResults = found && found.mode === 'law' ? found.results : []
  const canAddKeyword = mode === 'keyword' && query.trim().length >= 2
    && !watchedOf('keyword', query.trim())

  return (
    <div className="card block bz-law-card">
      <SectionHead title="전체 영향 법령 동향" canEdit onEdit={() => setEditing(true)}
                   extra={<span className="bz-chip bz-law-count">
                            법령 {lawItems.length} · 키워드 {kwItems.length}
                          </span>} />

      <div className="bz-law-watch">
        {pillRow('법령', lawItems, false)}
        {pillRow('키워드', kwItems, false)}
        <div className="h-sub bz-law-note">
          시행령 · 시행규칙 개정과, 본문에 키워드가 든 법령까지 함께 봅니다
        </div>
      </div>

      {/* 여섯 열이라 반폭 카드에서는 폭이 모자란다. 잘라 버리지 않고
          가로로 밀어 볼 수 있게 한다(전체 폭에서는 스크롤이 생기지 않는다). */}
      <div className="bz-law-scroll">
      <table className="tbl bz-doc-tbl bz-law-tbl">
        <thead>
          <tr>
            <th>구분</th>
            <th>법령명</th>
            <th>주관부처</th>
            <th>시행일</th>
            <th>개정 및 신설 내용</th>
            <th className="bz-law-ai-col">AI 제언</th>
          </tr>
        </thead>
        <tbody>
          {laws.length === 0 && (
            <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--ink-faint)', fontSize: 12 }}>
              {watched.length === 0 ? '담은 법령 · 키워드가 없습니다' : '동향 없음'}
            </td></tr>
          )}
          {laws.map(l => {
            const color = CAT_COLOR[l.category] || CAT_COLOR['기타']
            const name = l.short_name || l.law_name
            return (
              <tr key={l.id}>
                <td>
                  <span className="bz-chip" style={{
                    background: `color-mix(in srgb, ${color} 14%, transparent)`, color,
                  }}>{l.category}</span>
                </td>
                <th scope="row" title={name}>
                  {l.source_url ? (
                    <a className="bz-law-link" href={l.source_url} target="_blank" rel="noreferrer">
                      {name} <ExternalLink size={10} />
                    </a>
                  ) : name}
                </th>
                <td title={l.ministry}>{l.ministry || <span className="bz-muted">—</span>}</td>
                <td className="bz-nowrap">{l.date || <span className="bz-muted">—</span>}</td>
                <td title={l.summary || l.title}>
                  {l.summary || l.title || <span className="bz-muted">—</span>}
                </td>
                <td>
                  <button className="btn-ghost bz-law-ai" disabled={busyId === l.id}
                          onClick={() => onAdvise(l)}
                          title="이 법령이 우리 사업에 미칠 영향을 챗봇에 물어봅니다">
                    <Sparkles size={12} /> {busyId === l.id ? '여는 중' : '제언'}
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      </div>

      {editing && (
        <SectionModal title="관심 법령 · 키워드"
                      onClose={() => { setEditing(false); setQuery('') }}
                      hint="담은 것에 걸리는 개정만 동향 표에 올라갑니다 (자동 저장)">
          {error && <p className="note" style={{ color: 'var(--red)' }}>{error}</p>}

          <div className="bz-law-modes">
            {([['law', '법령명'], ['keyword', '키워드']] as const).map(([k, label]) => (
              <button key={k} className={`bz-law-mode${mode === k ? ' on' : ''}`}
                      onClick={() => { setMode(k); setQuery(''); setFound(null) }}>
                {label}
              </button>
            ))}
            <span className="h-sub bz-law-modehint">
              {mode === 'law'
                ? '그 법과 시행령 · 시행규칙 개정을 봅니다'
                : '개정 본문에 이 말이 들어간 법령을 봅니다 — 새로 생긴 법도 잡힙니다'}
            </span>
          </div>

          <div className="bz-law-search">
            <Search size={14} />
            <input className="inp" autoFocus value={query}
                   placeholder={mode === 'law' ? '법령명 (예: 농지법, 태양광)'
                                               : '키워드 (예: 태양광, 이격거리, 영농형)'}
                   onChange={e => setQuery(e.target.value)}
                   onKeyDown={e => {
                     if (e.key === 'Enter' && canAddKeyword) void add('keyword', query.trim())
                   }} />
            {mode === 'keyword' && (
              <button className="btn-primary bz-law-addkw" disabled={!canAddKeyword || !!busyTerm}
                      onClick={() => add('keyword', query.trim())}>
                <Plus size={13} /> 담기
              </button>
            )}
          </div>

          <div className="bz-law-block-title">지금 담은 것</div>
          {pillRow('법령', lawItems, true)}
          {pillRow('키워드', kwItems, true)}

          <div className="bz-law-block-title">
            {mode === 'law' ? '검색 결과' : '이 키워드에 걸리는 법령'}
            {found && (
              <span className="bz-chip bz-law-src"
                    style={found.source === 'live'
                      ? { background: 'var(--mint-soft)', color: 'var(--green-600)' }
                      : { background: 'color-mix(in srgb, var(--amber) 16%, transparent)', color: 'var(--amber)' }}>
                {found.source === 'live' ? '법제처 실시간' : '스냅샷'}
              </span>
            )}
          </div>
          {found && found.source === 'snapshot' && found.reason && (
            <p className="note">{found.reason}</p>
          )}

          {query.trim().length < 2 ? (
            <p className="note">두 글자 이상 입력하면 찾습니다.</p>
          ) : searching ? (
            <p className="note">찾는 중...</p>
          ) : mode === 'keyword' ? (
            kwPreview.length === 0 ? (
              <p className="note">이 말이 들어간 법령을 찾지 못했습니다.</p>
            ) : (
              <>
                <p className="note">
                  최신 시행일 순으로 {kwPreview.length}건까지 동향 표에 올라갑니다.
                </p>
                <div className="bz-law-results">
                  <table className="tbl bz-doc-tbl bz-law-pick">
                    <thead>
                      <tr>
                        <th>법령</th><th>주관부처</th>
                        <th className="bz-nowrap">시행일</th><th className="bz-nowrap">개정</th>
                      </tr>
                    </thead>
                    <tbody>
                      {kwPreview.map(l => (
                        <tr key={l.id}>
                          <th scope="row" title={l.law_name}>{l.law_name}</th>
                          <td title={l.ministry}>{l.ministry || <span className="bz-muted">—</span>}</td>
                          <td className="bz-nowrap">{l.date || <span className="bz-muted">—</span>}</td>
                          <td className="bz-nowrap">{l.category}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )
          ) : lawResults.length === 0 ? (
            <p className="note">찾은 법령이 없습니다.</p>
          ) : (
            <div className="bz-law-results">
              <table className="tbl bz-doc-tbl bz-law-pick">
                <thead>
                  <tr>
                    <th className="bz-law-pick-act" />
                    <th>법령</th>
                    <th>주관부처</th>
                    <th className="bz-nowrap">딸린 법령</th>
                    <th className="bz-nowrap">최근 시행</th>
                  </tr>
                </thead>
                <tbody>
                  {lawResults.map((c: LawSearchItem) => {
                    const on = !!watchedOf('law', c.family)
                    return (
                      <tr key={c.family} className={on ? 'bz-law-pick-on' : ''}>
                        <td>
                          <button className="btn-ghost bz-law-pick-btn" disabled={busyTerm === c.family}
                                  onClick={() => toggle('law', c.family)}
                                  title={on ? '동향에서 빼기' : '동향에 넣기'}>
                            {on ? <X size={13} /> : <Plus size={13} />}
                          </button>
                        </td>
                        <th scope="row" title={c.law_name}>{c.family}</th>
                        <td title={c.ministry}>{c.ministry || <span className="bz-muted">—</span>}</td>
                        <td className="bz-nowrap">{c.count}건</td>
                        <td className="bz-nowrap">{c.latest || <span className="bz-muted">—</span>}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </SectionModal>
      )}
    </div>
  )
}
