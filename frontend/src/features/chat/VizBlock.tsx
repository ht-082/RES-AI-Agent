import { useEffect, useMemo, useState } from 'react'
import TimelineBlock, { type TimelineItem } from './TimelineBlock'

/**
 * 구조화 시각화 블록의 진입점.
 *
 * LLM은 **데이터만** 내고 렌더는 앱이 소유한다 — TableChart가 표 DOM의 숫자를
 * 그대로 읽어 차트를 그리는 것과 같은 원칙이다. LLM에게 HTML이나 도식 문법을
 * 맡기면 디자인이 매번 달라지고, mermaid처럼 앱 테마와 겉도는 결과가 나온다.
 *
 * 형식:  ```viz:timeline  +  {"items":[...]}
 *
 * **스트리밍이 이 설계의 핵심 제약이다.**
 * 답변은 delta마다 content가 누적되고 그때마다 마크다운이 다시 렌더된다.
 * 즉 JSON이 완성되기 전에 수십 번 파싱을 시도하게 된다:
 *     ```viz:timeline
 *     {"items":[{"date":"2021.11.      ← 이 상태로 렌더된다
 * 파싱 실패를 곧바로 오류로 처리하면 답변 내내 경고 박스가 깜빡인다.
 * 그래서 "아직 오는 중"과 "정말 잘못됨"을 시간으로 가른다 —
 * 내용이 계속 바뀌는 동안은 조용히 기다리고, 멈춘 뒤에도 실패면 그때 폴백한다.
 */

/** 구조가 덜 온 것으로 보이는데도 이 시간 넘게 멈춰 있으면 잘린 응답으로 보고 폴백한다 */
const STALL_MS = 2500

interface Props {
  type: string
  source: string
}

/**
 * JSON이 "아직 오는 중"인지 "완결됐는데 잘못됐는지" 구조로 판정한다.
 *
 * 시간(디바운스)만으로 가르면 모델이 잠깐 멈출 때 폴백 박스가 깜빡인다.
 * 괄호 균형은 타이밍과 무관하게 결정적이다 — 문자열 리터럴 안의 괄호와
 * 이스케이프를 건너뛰며 세면 잘린 JSON은 반드시 불균형으로 잡힌다.
 */
function looksComplete(src: string): boolean {
  const s = src.trim()
  if (!s) return false
  let depth = 0
  let inStr = false
  let esc = false
  for (const ch of s) {
    if (esc) { esc = false; continue }
    if (inStr) {
      if (ch === '\\') esc = true
      else if (ch === '"') inStr = false
      continue
    }
    if (ch === '"') inStr = true
    else if (ch === '{' || ch === '[') depth++
    else if (ch === '}' || ch === ']') depth--
  }
  return !inStr && depth === 0
}

/** 배열형 데이터를 최소한의 표로라도 보여준다 — 스키마가 어긋나도 내용은 잃지 않는다 */
function FallbackTable({ rows }: { rows: Record<string, unknown>[] }) {
  const cols = useMemo(() => {
    const seen: string[] = []
    for (const r of rows) {
      for (const k of Object.keys(r)) if (!seen.includes(k)) seen.push(k)
    }
    return seen.slice(0, 6)
  }, [rows])

  return (
    <div className="viz-fallback">
      <div className="viz-fallback-note">도식 형식을 알아보지 못해 표로 표시합니다</div>
      <div className="md-table-wrap">
        <table>
          <thead><tr>{cols.map(c => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {cols.map(c => {
                  const v = r[c]
                  return <td key={c}>{Array.isArray(v) ? v.join(', ') : String(v ?? '')}</td>
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function VizBlock({ type, source }: Props) {
  const parsed = useMemo<unknown>(() => {
    try {
      return JSON.parse(source)
    } catch {
      return null
    }
  }, [source])

  // 구조가 미완이면 기다린다. 다만 잘린 응답이 영원히 로딩으로 남지 않도록
  // 일정 시간 후에는 폴백을 허용한다(2차 안전장치).
  const complete = useMemo(() => looksComplete(source), [source])
  const [stalled, setStalled] = useState(false)
  useEffect(() => {
    setStalled(false)
    const t = setTimeout(() => setStalled(true), STALL_MS)
    return () => clearTimeout(t)
  }, [source])

  const settled = complete || stalled

  if (parsed === null) {
    if (!settled) return <div className="viz-loading">도식 그리는 중…</div>
    return (
      <div className="viz-fallback">
        <div className="viz-fallback-note">도식 데이터를 읽지 못했습니다 · 원본을 표시합니다</div>
        <pre><code>{source}</code></pre>
      </div>
    )
  }

  const obj = parsed as Record<string, unknown>
  const items = Array.isArray(obj?.items) ? (obj.items as Record<string, unknown>[]) : null

  if (!items || items.length === 0) {
    if (!settled) return <div className="viz-loading">도식 그리는 중…</div>
    return Array.isArray(parsed)
      ? <FallbackTable rows={parsed as Record<string, unknown>[]} />
      : (
        <div className="viz-fallback">
          <div className="viz-fallback-note">도식 데이터에 items가 없습니다</div>
          <pre><code>{source}</code></pre>
        </div>
      )
  }

  if (type === 'timeline') {
    const valid = items.filter(it => it && (it.title || it.date))
    if (valid.length === 0) return <FallbackTable rows={items} />
    return <TimelineBlock items={valid as unknown as TimelineItem[]} title={String(obj.title ?? '')} />
  }

  // 아직 지원하지 않는 유형 — 내용은 보존한다
  return <FallbackTable rows={items} />
}
