import { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import SectionHead from './SectionHead'
import { formatKRW } from '../constants'
import type { OpsDaily } from '../types'

// 발전실적 · 재무실적 — 당일 / 1개월 / 사업년도 누적.
// 세 값을 저장하지 않고 일별 기록에서 그때그때 센다(양식 §1-1·1-2).
// 사업년도 = 매년 1월 1일 ~ 12월 31일.
const num = (v: string | number | null) => (v === null || v === '' ? null : Number(v))

function stats(rows: OpsDaily[]) {
  if (rows.length === 0) return null
  const sorted = [...rows].sort((a, b) => (a.date < b.date ? 1 : -1))   // 최신순
  const last = sorted[0]
  const lastDate = new Date(last.date)
  const monthAgo = new Date(lastDate); monthAgo.setDate(monthAgo.getDate() - 29)
  const yearStart = `${lastDate.getFullYear()}-01-01`

  const inMonth = sorted.filter(r => new Date(r.date) >= monthAgo)
  const inYear = sorted.filter(r => r.date >= yearStart)
  const sum = (list: OpsDaily[], key: 'generation_mwh' | 'revenue_krw') =>
    list.reduce((a, r) => a + (num(r[key]) ?? 0), 0)
  const avg = (list: OpsDaily[], key: 'pr_pct' | 'generation_mwh') => {
    const vs = list.map(r => num(r[key])).filter((v): v is number => v !== null)
    return vs.length ? vs.reduce((a, b) => a + b, 0) / vs.length : null
  }

  return {
    date: last.date,
    days: { month: inMonth.length, year: inYear.length },
    gen: { day: num(last.generation_mwh), month: avg(inMonth, 'generation_mwh'), year: sum(inYear, 'generation_mwh') },
    pr: { day: num(last.pr_pct), month: avg(inMonth, 'pr_pct'), year: avg(inYear, 'pr_pct') },
    rev: { day: num(last.revenue_krw), month: sum(inMonth, 'revenue_krw'), year: sum(inYear, 'revenue_krw') },
    monthly: monthlySeries(inYear),
  }
}

function monthlySeries(rows: OpsDaily[]) {
  const by = new Map<string, number>()
  rows.forEach(r => {
    const key = r.date.slice(0, 7)
    by.set(key, (by.get(key) || 0) + (num(r.generation_mwh) ?? 0))
  })
  return [...by.entries()].sort().map(([m, v]) => ({ month: m.slice(5) + '월', 발전량: Math.round(v) }))
}

const mwh = (v: number | null) => (v === null ? '—' : `${v.toLocaleString(undefined, { maximumFractionDigits: 1 })} MWh`)
const pct = (v: number | null) => (v === null ? '—' : `${v.toFixed(1)} %`)

export default function OpsPerformance({ rows, id }: { rows: OpsDaily[]; id?: string }) {
  const s = useMemo(() => stats(rows), [rows])

  const tiles = (label: string, values: Array<[string, string]>) => (
    <div className="bz-perf-block">
      <div className="bz-econ-block-title">{label}</div>
      <div className="bz-perf-tiles">
        {values.map(([k, v]) => (
          <div key={k} className="bz-perf-tile">
            <span className="bz-perf-label">{k}</span>
            <span className="bz-perf-val">{v}</span>
          </div>
        ))}
      </div>
    </div>
  )

  return (
    <div className="card block" id={id}>
      <SectionHead title="발전 · 재무 실적"
                   extra={s
                     ? <span className="bz-updated">최근 실적 {s.date}</span>
                     : undefined} />
      {!s ? (
        <p className="note">
          일별 실적이 아직 없습니다. 발전량 · PR · 매출을 날짜별로 넣으면
          당일 · 1개월 · 연 누적이 자동으로 계산됩니다.
        </p>
      ) : (
        <div className="bz-scroll bz-scroll-pair">
          {tiles('발전량', [
            ['당일', mwh(s.gen.day)],
            [`1개월 평균 (${s.days.month}일)`, mwh(s.gen.month)],
            ['연 누적', mwh(s.gen.year)],
          ])}
          {tiles('PR', [
            ['당일', pct(s.pr.day)],
            ['1개월 평균', pct(s.pr.month)],
            ['연 평균', pct(s.pr.year)],
          ])}
          {tiles('매출', [
            ['당일', s.rev.day === null ? '—' : formatKRW(s.rev.day)],
            ['1개월', formatKRW(s.rev.month)],
            ['연 누적', formatKRW(s.rev.year)],
          ])}

          {s.monthly.length > 0 && (
            <>
              <div className="bz-econ-block-title">월별 발전량 (올해)</div>
              <div style={{ height: 190 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={s.monthly} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--line-soft)" vertical={false} />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v) => `${Number(v).toLocaleString()} MWh`} />
                    <Bar dataKey="발전량" fill="var(--brand)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
