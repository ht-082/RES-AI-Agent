import { useRef, useState } from 'react'
import { ArrowDown, ArrowUp, Download, History, Plus, Trash2, Upload } from 'lucide-react'
import { apiSend, apiUpload } from '../api'
import { ddayLabel, STATUS_META, STATUS_ORDER, STATUS_PROG } from '../constants'
import type { PermitStage } from '../types'

const GLYPH: Record<string, string> = { done: '✓', active: '◐', wait: '…', risk: '!', idle: '·' }

// 인허가 상세 진척도 — 원본 project.html 카드7 이식.
// tier 그룹핑(major 헤드 + minor 들여쓰기), 상태 pill 순환, 문서 버전관리, 단계 관리.
export default function PermitStagesCard({ siteId, stages, canEdit, onChanged }: {
  siteId: string
  stages: PermitStage[]
  canEdit: boolean
  onChanged: () => void
}) {
  const [error, setError] = useState('')
  const [openHistory, setOpenHistory] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const [nf, setNf] = useState({ name: '', tier: 'minor', agency: '' })
  const uploadTarget = useRef<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const fail = (e: unknown, fb: string) => setError(e instanceof Error ? e.message : fb)

  // 상태 순환: idle→wait→active→risk→done + progress 동기화 (원본 cycleStatus)
  const cycle = async (stage: PermitStage) => {
    if (!canEdit) return
    const next = STATUS_ORDER[(STATUS_ORDER.indexOf(stage.status) + 1) % STATUS_ORDER.length]
    try {
      await apiSend('PATCH', `/api/bizdev/stages/${stage.id}/`,
        { status: next, progress_pct: STATUS_PROG[next] })
      onChanged()
    } catch (e) { fail(e, '상태 변경 실패') }
  }

  const move = async (idx: number, dir: -1 | 1) => {
    const to = idx + dir
    if (to < 0 || to >= stages.length) return
    const ids = stages.map(s => s.id)
    ;[ids[idx], ids[to]] = [ids[to], ids[idx]]
    try {
      await apiSend('POST', '/api/bizdev/stages/reorder/', { site: siteId, ordered_ids: ids })
      onChanged()
    } catch (e) { fail(e, '순서 변경 실패') }
  }

  const removeStage = async (stage: PermitStage) => {
    if (!confirm(`"${stage.name}" 단계를 삭제할까요? 문서도 함께 삭제됩니다.`)) return
    try {
      await apiSend('DELETE', `/api/bizdev/stages/${stage.id}/`)
      onChanged()
    } catch (e) { fail(e, '삭제 실패') }
  }

  const addStage = async () => {
    if (!nf.name.trim()) { setError('단계명을 입력하세요.'); return }
    try {
      await apiSend('POST', '/api/bizdev/stages/', {
        site: siteId, name: nf.name.trim(), tier: nf.tier, agency: nf.agency.trim(),
        status: 'idle', progress_pct: 0, doc_label: '문서',
      })
      setAdding(false); setNf({ name: '', tier: 'minor', agency: '' }); setError('')
      onChanged()
    } catch (e) { fail(e, '단계 추가 실패') }
  }

  const pickFile = (stageId: string) => {
    uploadTarget.current = stageId
    fileInput.current?.click()
  }

  const upload = async (file: File | undefined) => {
    const stageId = uploadTarget.current
    if (!file || !stageId) return
    const form = new FormData()
    form.append('file', file)
    try {
      await apiUpload(`/api/bizdev/stages/${stageId}/documents/`, form)
      onChanged()
    } catch (e) { fail(e, '업로드 실패') }
    if (fileInput.current) fileInput.current.value = ''
  }

  const setCurrent = async (docId: string) => {
    try {
      await apiSend('POST', `/api/bizdev/documents/${docId}/set-current/`)
      onChanged()
    } catch (e) { fail(e, '최신 지정 실패') }
  }

  const removeDoc = async (docId: string) => {
    if (!confirm('이 버전을 삭제할까요?')) return
    try {
      await apiSend('DELETE', `/api/bizdev/documents/${docId}/`)
      onChanged()
    } catch (e) { fail(e, '문서 삭제 실패') }
  }

  return (
    <div className="card block">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3>인허가 상세 진척도</h3>
        {canEdit && (
          <button className="btn-ghost" style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}
                  onClick={() => setAdding(v => !v)}>
            <Plus size={13} /> 단계 추가
          </button>
        )}
      </div>
      <div className="h-sub" style={{ marginBottom: 12 }}>상태 배지 클릭 → 미착수→대기→진행중→리스크→완료 순환</div>

      {adding && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          <input className="inp" style={{ flex: 1, minWidth: 160 }} placeholder="단계명 *" value={nf.name}
                 onChange={e => setNf({ ...nf, name: e.target.value })} />
          <select className="inp" style={{ width: 90 }} value={nf.tier}
                  onChange={e => setNf({ ...nf, tier: e.target.value })}>
            <option value="minor">하위</option><option value="major">상위</option>
          </select>
          <input className="inp" style={{ width: 150 }} placeholder="관장 기관" value={nf.agency}
                 onChange={e => setNf({ ...nf, agency: e.target.value })} />
          <button className="btn-primary" onClick={addStage}>추가</button>
        </div>
      )}
      {error && <p className="note" style={{ color: 'var(--red)', marginBottom: 8 }}>{error}</p>}

      <input ref={fileInput} type="file" style={{ display: 'none' }}
             onChange={e => upload(e.target.files?.[0])} />

      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {stages.map((stage, idx) => {
          const meta = STATUS_META[stage.status]
          const current = stage.documents.find(d => d.is_current)
          const dday = ddayLabel(stage.deadline, stage.dday_label)
          const sub = stage.detail
            || [stage.agency, stage.received_date ? `접수 ${stage.received_date}` : '']
              .filter(Boolean).join(' · ')
          return (
            <div key={stage.id} className={`bz-stage ${stage.tier === 'major' ? 'major' : 'minor'}`}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="bz-stage-glyph" style={{ color: meta.color, borderColor: meta.color }}>
                  {GLYPH[stage.status]}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 12.5, fontWeight: stage.tier === 'major' ? 700 : 600 }}>
                      {stage.stage_no}. {stage.name}
                    </span>
                    {stage.tier === 'major' && (
                      <span className="bz-chip" style={{ background: 'var(--mint-soft)', color: 'var(--green-600)' }}>상위</span>
                    )}
                  </div>
                  {sub && <div style={{ fontSize: 10.5, color: 'var(--ink-faint)', marginTop: 1 }}>{sub}</div>}
                </div>

                <div className="bz-bar" style={{ width: 110, flexShrink: 0 }}>
                  <div className="bz-bar-fill" style={{ width: `${stage.progress_pct}%`, background: meta.color }} />
                </div>

                {/* 문서 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
                  {current ? (
                    <a className="btn-ghost" style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 3, textDecoration: 'none' }}
                       href={`/api/bizdev/documents/${current.id}/download/`} target="_blank" rel="noreferrer">
                      <Download size={12} /> {stage.doc_label} v{current.version}
                    </a>
                  ) : (
                    <span style={{ fontSize: 11, color: 'var(--ink-faint)' }}>미취득</span>
                  )}
                  {canEdit && (
                    <button className="btn-ghost" style={{ padding: 4 }} title={current ? '새 버전 업로드' : '업로드'}
                            onClick={() => pickFile(stage.id)}>
                      <Upload size={13} />
                    </button>
                  )}
                  {stage.documents.length > 0 && (
                    <button className="btn-ghost" style={{ padding: 4 }} title={`이력 ${stage.documents.length}`}
                            onClick={() => setOpenHistory(h => h === stage.id ? null : stage.id)}>
                      <History size={13} />
                    </button>
                  )}
                </div>

                <span className="bz-chip" onClick={() => cycle(stage)} style={{
                  background: `color-mix(in srgb, ${meta.color} 14%, transparent)`,
                  color: meta.color, cursor: canEdit ? 'pointer' : 'default',
                  minWidth: 46, textAlign: 'center', flexShrink: 0,
                }}>{meta.label}</span>
                <span style={{ fontSize: 10.5, color: 'var(--ink-faint)', width: 52, textAlign: 'right', flexShrink: 0 }}>
                  {dday}
                </span>

                {canEdit && (
                  <span style={{ display: 'flex', gap: 1, flexShrink: 0 }}>
                    <button className="btn-ghost" style={{ padding: 2 }} onClick={() => move(idx, -1)} aria-label="위로"><ArrowUp size={12} /></button>
                    <button className="btn-ghost" style={{ padding: 2 }} onClick={() => move(idx, 1)} aria-label="아래로"><ArrowDown size={12} /></button>
                    <button className="btn-ghost" style={{ padding: 2 }} onClick={() => removeStage(stage)} aria-label="삭제"><Trash2 size={12} /></button>
                  </span>
                )}
              </div>

              {/* 버전 이력 */}
              {openHistory === stage.id && (
                <div className="bz-doc-history">
                  {stage.documents.map(doc => (
                    <div key={doc.id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5 }}>
                      <span style={{ fontWeight: 700, width: 28 }}>v{doc.version}</span>
                      {doc.is_current && (
                        <span className="bz-chip" style={{ background: 'var(--mint-soft)', color: 'var(--green-600)' }}>최신</span>
                      )}
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {doc.file_name}{doc.note ? ` — ${doc.note}` : ''}
                      </span>
                      <a href={`/api/bizdev/documents/${doc.id}/download/`} target="_blank" rel="noreferrer"
                         className="btn-ghost" style={{ padding: 3 }} title="받기"><Download size={12} /></a>
                      {canEdit && !doc.is_current && (
                        <button className="btn-ghost" style={{ padding: '2px 6px', fontSize: 11 }}
                                onClick={() => setCurrent(doc.id)}>최신 지정</button>
                      )}
                      {canEdit && (
                        <button className="btn-ghost" style={{ padding: 3 }} onClick={() => removeDoc(doc.id)} aria-label="삭제">
                          <Trash2 size={12} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
