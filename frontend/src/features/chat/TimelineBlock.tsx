import { useMemo, useState } from 'react'

/**
 * 연혁·경과 타임라인.
 *
 * **왜 mermaid timeline을 쓰지 않는가**
 * mermaid의 timeline은 이벤트를 가로로 배치한다. 채팅 본문은 820px 고정 폭이라
 * 이벤트가 6개만 넘어도 칸당 70px로 압축되고 한글이 읽히지 않는다(실측: 11개 → 판독 불가).
 * 게다가 timeline 유형은 themeVariables를 무시하고 자체 무지개 팔레트를 써서
 * 앱 디자인과 겉돈다. 세로 배치는 이벤트가 늘어도 글자 크기가 본문과 같다.
 *
 * 요약 수치(총 기간·완료 건수)는 **여기서 계산한다.** LLM이 쓴 숫자를 그대로 믿으면
 * 항목과 요약이 어긋날 수 있다 — TableChart가 표의 숫자만 쓰는 것과 같은 이유다.
 */

export interface TimelineItem {
  date?: string
  phase?: string
  title?: string
  detail?: string
  tags?: string[]
  status?: 'done' | 'ongoing' | 'planned'
}

/** '2021.11.30' · '2021-11' · '2021.11' 을 월 단위 정수로 (정렬·기간 계산용) */
function toMonths(raw?: string): number | null {
  if (!raw) return null
  const m = raw.match(/(\d{4})\D+(\d{1,2})/)
  if (!m) return null
  return parseInt(m[1], 10) * 12 + parseInt(m[2], 10)
}

function statusOf(it: TimelineItem): 'done' | 'ongoing' | 'planned' {
  if (it.status === 'ongoing' || it.status === 'planned') return it.status
  return 'done'
}

export default function TimelineBlock({ items, title }: { items: TimelineItem[]; title?: string }) {
  const [mode, setMode] = useState<'timeline' | 'table'>('timeline')

  const meta = useMemo(() => {
    const ms = items.map(i => toMonths(i.date)).filter((v): v is number => v !== null)
    const done = items.filter(i => statusOf(i) === 'done').length
    const ongoing = items.filter(i => statusOf(i) === 'ongoing').length
    const span = ms.length >= 2 ? Math.max(...ms) - Math.min(...ms) : null
    return { span, done, ongoing, first: items[0]?.date, last: items[items.length - 1]?.date }
  }, [items])

  return (
    <div className="viz-timeline">
      <div className="vt-head">
        <div className="vt-title">{title || '경과'}</div>
        <div className="vt-meta">
          {meta.first && meta.last && <span>{meta.first} – {meta.last}</span>}
          {meta.span !== null && <span>총 {meta.span}개월</span>}
          <span>완료 {meta.done}건</span>
          {meta.ongoing > 0 && <span>진행 {meta.ongoing}건</span>}
        </div>
      </div>

      {mode === 'timeline' ? (
        <div className="vt-list">
          {items.map((it, i) => {
            const st = statusOf(it)
            const last = i === items.length - 1
            return (
              <div className="vt-row" key={i}>
                <div className="vt-date">{it.date}</div>
                <div className="vt-rail">
                  <span className={`vt-dot vt-${st}`} />
                  {!last && <span className="vt-line" />}
                </div>
                <div className={last ? 'vt-body vt-body-last' : 'vt-body'}>
                  {it.phase && <span className={`vt-phase vt-phase-${st}`}>{it.phase}</span>}
                  {it.title && <div className="vt-name">{it.title}</div>}
                  {it.detail && <div className="vt-detail">{it.detail}</div>}
                  {it.tags && it.tags.length > 0 && (
                    <div className="vt-tags">
                      {it.tags.map((t, ti) => <span className="vt-tag" key={ti}>{t}</span>)}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="md-table-wrap">
          <table>
            <thead><tr><th>시점</th><th>구분</th><th>내용</th></tr></thead>
            <tbody>
              {items.map((it, i) => (
                <tr key={i}>
                  <td>{it.date}</td>
                  <td>{it.phase || ''}</td>
                  <td>
                    {it.title}
                    {it.detail ? ` — ${it.detail}` : ''}
                    {it.tags?.length ? ` (${it.tags.join(' · ')})` : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="vt-tools">
        <button
          className={mode === 'timeline' ? 'tt-btn is-on' : 'tt-btn'}
          onClick={() => setMode('timeline')}
        >타임라인</button>
        <button
          className={mode === 'table' ? 'tt-btn is-on' : 'tt-btn'}
          onClick={() => setMode('table')}
        >표</button>
      </div>
    </div>
  )
}
