import { useMemo, useState, type ReactNode } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

/**
 * 답변 안의 표를 차트로 전환한다.
 *
 * **수치 정확성이 최우선**이라는 요구에 맞춘 설계다.
 * LLM에게 차트 값을 따로 쓰게 하면 환각이 그대로 그림에 박히고, 표는 틀리면
 * 눈에 띄지만 차트는 그럴듯해 보여 더 위험하다.
 * 그래서 여기서는 **이미 화면에 있는 표의 숫자를 그대로 파싱**해서 쓴다.
 * 차트를 켜도 표는 아래에 그대로 남아 대조할 수 있다.
 */

const PALETTE = ['#2f7f6c', '#c98b2e', '#5b8cb8', '#8a6ea8', '#b8635b', '#4f8f52']

interface Row { label: string; [k: string]: string | number }

/** "1,606.3억원" → 1606.3 · 숫자를 못 찾으면 null */
function toNumber(raw: string): number | null {
  if (!raw) return null
  const cleaned = raw.replace(/[,\s]/g, '')
  const m = cleaned.match(/-?\d+(?:\.\d+)?/)
  if (!m) return null
  const v = parseFloat(m[0])
  return Number.isFinite(v) ? v : null
}

/** 표 DOM에서 헤더와 셀을 읽어 차트용 데이터로 만든다 */
function parseTable(node: HTMLTableElement) {
  const headers = Array.from(node.querySelectorAll('thead th'))
    .map(th => (th.textContent ?? '').trim())
  const bodyRows = Array.from(node.querySelectorAll('tbody tr'))

  if (headers.length < 2 || bodyRows.length === 0) return null

  // 값이 숫자인 열만 골라낸다 (첫 열은 라벨로 쓴다)
  const numericCols: number[] = []
  for (let c = 1; c < headers.length; c++) {
    const parsed = bodyRows
      .map(tr => toNumber((tr.children[c]?.textContent ?? '').trim()))
      .filter(v => v !== null)
    // 절반 이상이 숫자로 읽히면 수치 열로 인정
    if (parsed.length >= Math.ceil(bodyRows.length / 2)) numericCols.push(c)
  }
  if (numericCols.length === 0) return null

  const rows: Row[] = []
  for (const tr of bodyRows) {
    const label = (tr.children[0]?.textContent ?? '').trim()
    if (!label) continue
    const row: Row = { label }
    let has = false
    for (const c of numericCols) {
      const v = toNumber((tr.children[c]?.textContent ?? '').trim())
      if (v !== null) { row[headers[c]] = v; has = true }
    }
    if (has) rows.push(row)
  }
  if (rows.length === 0) return null

  return { rows, series: numericCols.map(c => headers[c]) }
}

export default function TableChart({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<'table' | 'bar' | 'line'>('table')
  const [host, setHost] = useState<HTMLDivElement | null>(null)

  const data = useMemo(() => {
    if (!host) return null
    const table = host.querySelector('table')
    return table ? parseTable(table as HTMLTableElement) : null
  }, [host, mode])

  const chartable = !!data

  return (
    <div className="table-wrap" ref={setHost}>
      {chartable && (
        <div className="table-tools">
          <button
            className={mode === 'table' ? 'tt-btn is-on' : 'tt-btn'}
            onClick={() => setMode('table')}
          >표</button>
          <button
            className={mode === 'bar' ? 'tt-btn is-on' : 'tt-btn'}
            onClick={() => setMode('bar')}
            title="표의 숫자를 그대로 사용합니다"
          >막대</button>
          <button
            className={mode === 'line' ? 'tt-btn is-on' : 'tt-btn'}
            onClick={() => setMode('line')}
            title="표의 숫자를 그대로 사용합니다"
          >선</button>
        </div>
      )}

      {/* 표는 항상 DOM에 유지한다 — 차트가 이 DOM을 읽어 그리고,
          사용자가 차트와 원본 수치를 대조할 수 있어야 하기 때문이다 */}
      <div className={mode === 'table' ? '' : 'table-hidden'}>{children}</div>

      {mode !== 'table' && data && (
        <>
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={260}>
              {mode === 'bar' ? (
                <BarChart data={data.rows} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  {data.series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
                  {data.series.map((s, i) => (
                    <Bar key={s} dataKey={s} fill={PALETTE[i % PALETTE.length]}>
                      {data.series.length === 1 &&
                        data.rows.map((_, ri) => (
                          <Cell key={ri} fill={PALETTE[ri % PALETTE.length]} />
                        ))}
                    </Bar>
                  ))}
                </BarChart>
              ) : (
                <LineChart data={data.rows} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  {data.series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
                  {data.series.map((s, i) => (
                    <Line key={s} type="monotone" dataKey={s}
                          stroke={PALETTE[i % PALETTE.length]} strokeWidth={2} dot />
                  ))}
                </LineChart>
              )}
            </ResponsiveContainer>
          </div>
          <div className="chart-note">
            표의 숫자를 그대로 사용했습니다 · 단위는 원본 표를 확인하세요
          </div>
        </>
      )}
    </div>
  )
}
