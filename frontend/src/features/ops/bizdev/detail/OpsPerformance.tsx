import { useMemo, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Plus, Trash2 } from 'lucide-react'
import SectionHead, { lastEdited } from './SectionHead'
import SectionModal from './SectionModal'
import { EditableText } from './editors'
import { apiSend } from '../api'
import { formatKRW } from '../constants'
import type { OpsDaily } from '../types'

// 발전실적 · 재무실적 — 당일 / 1개월 / 사업년도 누적.
// 세 값을 저장하지 않고 일별 기록에서 그때그때 센다(양식 §1-1·1-2).
// 사업년도 = 매년 1월 1일 ~ 12월 31일.
// 담는 것은 '하루 한 줄' 뿐이라, 편집도 그 줄을 고치는 것으로 끝난다.
const num = (v: string | number | null) => (v === null || v === '' ? null : Number(v))

// 표에 친 값을 서버로 보낼 모양으로. 빈 칸은 0 이 아니라 null 이다
// (0 으로 저장하면 '발전을 안 했다' 와 '아직 안 넣었다' 가 섞인다).
const toValue = (text: string) => {
  const t = text.trim().replace(/,/g, '')
  if (t === '') return null
  return Number.isFinite(Number(t)) ? t : null
}

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

// 1~12월을 늘 같은 자리에 둔다 — 달이 없다고 축이 줄면 해마다 그래프가
// 달라 보인다. 실적이 없는 달은 0 이 아니라 빈칸으로 두어 선을 끊는다
// (0 으로 채우면 발전을 안 한 것처럼 읽힌다).
function monthlySeries(rows: OpsDaily[]) {
  const sum = new Map<number, number>()
  rows.forEach(r => {
    const m = Number(r.date.slice(5, 7))
    const v = num(r.generation_mwh)
    if (v === null) return
    sum.set(m, (sum.get(m) || 0) + v)
  })
  return Array.from({ length: 12 }, (_, i) => ({
    month: `${i + 1}월`,
    발전량: sum.has(i + 1) ? Math.round(sum.get(i + 1)!) : null,
  }))
}

// 같은 사업의 같은 날짜는 한 줄뿐이다(DB 제약). 새 줄은 오늘부터 거슬러
// 올라가며 비어 있는 첫 날에 만든다 — 오늘 것이 이미 있는데 또 누르면
// 서버가 400 을 돌려줄 뿐이라, 눌러서 되는 날짜를 골라 준다.
function nextFreeDate(rows: OpsDaily[]) {
  const taken = new Set(rows.map(r => r.date))
  const d = new Date()
  for (let i = 0; i < 400; i++) {
    const iso = new Date(d.getTime() - i * 86400000).toISOString().slice(0, 10)
    if (!taken.has(iso)) return iso
  }
  return new Date().toISOString().slice(0, 10)
}

const mwh = (v: number | null) => (v === null ? '—' : `${v.toLocaleString(undefined, { maximumFractionDigits: 1 })} MWh`)
const pct = (v: number | null) => (v === null ? '—' : `${v.toFixed(1)} %`)

export default function OpsPerformance({ rows, siteId, canEdit, onChanged, onError, id }: {
  rows: OpsDaily[]
  siteId: string
  canEdit: boolean
  onChanged: () => void
  onError: (msg: string) => void
  id?: string
}) {
  const s = useMemo(() => stats(rows), [rows])
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)

  const fail = (e: unknown, fb: string) => onError(e instanceof Error ? e.message : fb)

  const patch = async (row: OpsDaily, body: Record<string, unknown>) => {
    await apiSend('PATCH', `/api/bizdev/ops-daily/${row.id}/`, body)
    onChanged()
  }
  const add = async () => {
    setBusy(true)
    try {
      await apiSend('POST', '/api/bizdev/ops-daily/', {
        site: siteId, date: nextFreeDate(rows),
      })
      onChanged()
    } catch (e) { fail(e, '추가 실패') } finally { setBusy(false) }
  }
  const remove = async (row: OpsDaily) => {
    if (!confirm(`${row.date} 실적을 삭제할까요?`)) return
    try {
      await apiSend('DELETE', `/api/bizdev/ops-daily/${row.id}/`)
      onChanged()
    } catch (e) { fail(e, '삭제 실패') }
  }

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

  // 편집표 — 날짜 · 발전량 · PR · 매출 · 비고. 요약은 여기서 다시 센다.
  const editTable = () => (
    <table className="tbl bz-doc-tbl bz-daily-tbl">
      <thead>
        <tr>
          <th>날짜</th>
          <th className="bz-num">발전량 (MWh)</th>
          <th className="bz-num">PR (%)</th>
          <th className="bz-num">매출 (원)</th>
          <th>비고</th>
          {canEdit && <th className="bz-col-act" />}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 && (
          <tr><td colSpan={canEdit ? 6 : 5}
                  style={{ textAlign: 'center', color: 'var(--ink-faint)', fontSize: 12 }}>
            아직 기록이 없습니다. '실적 추가' 를 눌러 하루치를 넣어 주세요.
          </td></tr>
        )}
        {rows.map(row => (
          <tr key={row.id}>
            <td className="bz-nowrap">
              <input className="bz-cell-input" type="date" value={row.date} disabled={!canEdit}
                     onChange={e => {
                       if (!e.target.value) return
                       patch(row, { date: e.target.value }).catch(x => fail(x, '날짜 저장 실패'))
                     }} />
            </td>
            <td className="bz-num">
              <EditableText value={row.generation_mwh ?? ''} disabled={!canEdit} placeholder="—"
                            onSave={v => patch(row, { generation_mwh: toValue(v) })} />
            </td>
            <td className="bz-num">
              <EditableText value={row.pr_pct ?? ''} disabled={!canEdit} placeholder="—"
                            onSave={v => patch(row, { pr_pct: toValue(v) })} />
            </td>
            <td className="bz-num">
              <EditableText value={row.revenue_krw === null ? '' : String(row.revenue_krw)}
                            disabled={!canEdit} placeholder="—"
                            onSave={v => patch(row, { revenue_krw: toValue(v) })} />
            </td>
            <td title={row.note}>
              <EditableText value={row.note} disabled={!canEdit} placeholder="특이사항"
                            onSave={v => patch(row, { note: v })} />
            </td>
            {canEdit && (
              <td>
                <button className="btn-ghost" style={{ padding: 3 }} onClick={() => remove(row)}
                        aria-label="삭제"><Trash2 size={13} /></button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  )

  return (
    <div className="card block" id={id}>
      <SectionHead title="발전 · 재무 실적"
                   updatedAt={lastEdited(rows.map(r => r.updated_at))}
                   canEdit={canEdit} onEdit={() => setEditing(true)}
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

          {s.monthly.some(m => m.발전량 !== null) && (
            <>
              <div className="bz-econ-block-title">월별 발전량 (올해)</div>
              <div style={{ height: 190 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={s.monthly} margin={{ top: 6, right: 10, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--line-soft)" vertical={false} />
                    <XAxis dataKey="month" tick={{ fontSize: 10.5 }} interval={0} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v) => `${Number(v).toLocaleString()} MWh`} />
                    <Line type="monotone" dataKey="발전량" stroke="var(--brand)" strokeWidth={2}
                          dot={{ r: 3 }} activeDot={{ r: 5 }} connectNulls={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>
      )}

      {editing && (
        <SectionModal title="발전 · 재무 실적"
                      hint="하루에 한 줄씩 넣습니다 — 당일 · 1개월 · 연 누적은 이 줄들로 계산합니다"
                      onClose={() => { setEditing(false); onChanged() }}>
          {canEdit && (
            <button className="btn-ghost" style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}
                    onClick={add} disabled={busy}><Plus size={13} /> 실적 추가</button>
          )}
          <div className="bz-daily-scroll">{editTable()}</div>
        </SectionModal>
      )}
    </div>
  )
}
