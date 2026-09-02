import { useRef, useState } from 'react'
import { ArrowDown, ArrowUp, Download, History, Plus, Trash2, Upload } from 'lucide-react'
import { apiSend, apiUpload } from '../api'
import { CERTAINTY_META, ddayLabel, STATUS_META } from '../constants'
import { CertaintyCell, EditableSelect, EditableText } from './editors'
import SectionModal from './SectionModal'
import SectionHead, { lastEdited } from './SectionHead'
import PipelineStrip from './PipelineStrip'
import Lines from './Lines'
import type { PermitStage } from '../types'

const STATE_OPTIONS: Array<[string, string]> = [
  ['done', '완료'], ['active', '진행중'], ['idle', '미착수'], ['na', '미대상'],
]
// 원본(project.page.js ST)의 상태 글리프
const GLYPH: Record<string, string> = { done: '✓', active: '◐', idle: '·', na: '—' }
// 원본의 단계별 진척 바 — 4단계 상태에서 파생시킨다(별도 값을 두지 않는다)
const BAR: Record<string, number> = { done: 100, active: 50, idle: 0, na: 0 }

// 인허가 현황 — 원본 '인허가 상세 진척도' 카드 배치에 사업개요 양식의
// 내용·확정도·특이사항을 얹었다. 3-1 법정절차 / 3-2 개별법 협의로 묶는다.
export default function PermitSection({ siteId, stages, canEdit, onChanged, onError }: {
  siteId: string
  stages: PermitStage[]
  canEdit: boolean
  onChanged: () => void
  onError: (msg: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [openHistory, setOpenHistory] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const uploadTarget = useRef<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const fail = (e: unknown, fb: string) => onError(e instanceof Error ? e.message : fb)

  const patch = async (stage: PermitStage, body: Record<string, unknown>) => {
    await apiSend('PATCH', `/api/bizdev/stages/${stage.id}/`, body)
    onChanged()
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

  // 순서 이동 — 서버가 1..n 으로 다시 매기므로 사업 전체 순서를 보낸다
  const move = async (group: PermitStage[], idx: number, dir: -1 | 1) => {
    const to = idx + dir
    if (to < 0 || to >= group.length) return
    const ids = [...stages].sort((a, b) => a.stage_no - b.stage_no).map(s => s.id)
    const from = ids.indexOf(group[idx].id)
    const dest = ids.indexOf(group[to].id)
    ids[from] = group[to].id
    ids[dest] = group[idx].id
    try {
      await apiSend('POST', '/api/bizdev/stages/reorder/', { site: siteId, ordered_ids: ids })
      onChanged()
    } catch (e) { fail(e, '순서 변경 실패') }
  }

  const addStage = async (category: 'statutory' | 'individual') => {
    setBusy(true)
    try {
      await apiSend('POST', '/api/bizdev/stages/', {
        site: siteId, name: '새 항목', category, agency: '', status: 'idle',
        certainty: 'unconfirmed', doc_label: '문서',
        tier: category === 'statutory' ? 'major' : 'minor',
      })
      onChanged()
    } catch (e) { fail(e, '항목 추가 실패') } finally { setBusy(false) }
  }

  const removeStage = async (stage: PermitStage) => {
    if (!confirm(`"${stage.name}" 항목을 삭제할까요? 붙어 있는 문서도 함께 지워집니다.`)) return
    try {
      await apiSend('DELETE', `/api/bizdev/stages/${stage.id}/`)
      onChanged()
    } catch (e) { fail(e, '삭제 실패') }
  }

  // 항목 한 장 — 원본 stageRow 배치(글리프 | 본문 | 우측 상태)
  const stageRow = (stage: PermitStage, group: PermitStage[], idx: number, editable: boolean) => {
    const meta = STATUS_META[stage.status]
    const cert = CERTAINTY_META[stage.certainty]
    const current = stage.documents.find(d => d.is_current)
    const dday = ddayLabel(stage.deadline, stage.dday_label)

    return (
      <div key={stage.id} className="bz-stage2">
        <span className="bz-stage-glyph2" style={{ background: meta.color }}>
          {GLYPH[stage.status]}
        </span>

        <div className="bz-stage-body">
          <div className="bz-stage-title">
            {editable
              ? <EditableText value={stage.name} disabled={!canEdit} placeholder="항목명"
                              onSave={v => patch(stage, { name: v })} />
              : <span className="bz-stage-name">{stage.name}</span>}
            {editable
              ? <EditableText value={stage.agency} disabled={!canEdit} placeholder="관할 기관"
                              onSave={v => patch(stage, { agency: v })} />
              : stage.agency && <span className="bz-stage-agency">{stage.agency}</span>}
          </div>

          {editable
            ? <EditableText value={stage.content} multiline disabled={!canEdit}
                            placeholder="내용 (허가번호 · 용량 · 일자 등)"
                            onSave={v => patch(stage, { content: v })} />
            : <div className="bz-stage-content"><Lines text={stage.content} /></div>}

          <div className="bz-bar bz-stage-bar">
            <div className="bz-bar-fill"
                 style={{ width: `${BAR[stage.status]}%`, background: meta.color }} />
          </div>

          <div className="bz-stage-remark">
            <span className="bz-stage-tag">특이사항</span>
            {editable
              ? <EditableText value={stage.remark} multiline disabled={!canEdit} placeholder="—"
                              onSave={v => patch(stage, { remark: v })} />
              : <Lines text={stage.remark} />}
          </div>

          <div className="bz-stage-docs">
            {current ? (
              <a className="btn-ghost bz-doc-btn" target="_blank" rel="noreferrer"
                 href={`/api/bizdev/documents/${current.id}/download/`}>
                <Download size={12} /> {stage.doc_label || '문서'} v{current.version}
              </a>
            ) : <span className="bz-doc-none">미취득</span>}
            {canEdit && editable && (
              <button className="btn-ghost bz-doc-btn"
                      onClick={() => { uploadTarget.current = stage.id; fileInput.current?.click() }}>
                <Upload size={12} /> {current ? '새 버전' : '업로드'}
              </button>
            )}
            {stage.documents.length > 0 && (
              <button className="btn-ghost bz-doc-btn"
                      onClick={() => setOpenHistory(h => (h === stage.id ? null : stage.id))}>
                <History size={12} /> 이력({stage.documents.length})
              </button>
            )}
          </div>

          {openHistory === stage.id && (
            <div className="bz-doc-history">
              {[...stage.documents].sort((a, b) => b.version - a.version).map(doc => (
                <div key={doc.id} className="bz-doc-row">
                  <span className="bz-doc-ver">v{doc.version}</span>
                  {doc.is_current && (
                    <span className="bz-chip"
                          style={{ background: 'var(--mint-soft)', color: 'var(--green-600)' }}>최신</span>
                  )}
                  <span className="bz-doc-name" title={doc.file_name}>{doc.file_name}</span>
                  <a className="bz-doc-link" target="_blank" rel="noreferrer"
                     href={`/api/bizdev/documents/${doc.id}/download/`}>받기</a>
                  {canEdit && editable && !doc.is_current && (
                    <button className="bz-doc-link" onClick={() => setCurrent(doc.id)}>최신 지정</button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bz-stage-side">
          {editable ? (
            <EditableSelect value={stage.status} options={STATE_OPTIONS} disabled={!canEdit}
                            onSave={v => patch(stage, { status: v })}
                            style={{
                              color: meta.color, fontWeight: 700, fontSize: 11, width: 76,
                              background: `color-mix(in srgb, ${meta.color} 12%, transparent)`,
                              borderRadius: 6, textAlign: 'center',
                            }} />
          ) : (
            <span className="bz-chip" style={{
              background: `color-mix(in srgb, ${meta.color} 12%, transparent)`, color: meta.color,
            }}>{meta.label}</span>
          )}

          {editable ? (
            <CertaintyCell value={stage.certainty} disabled={!canEdit}
                           onSave={v => patch(stage, { certainty: v })} />
          ) : (
            <span className="bz-chip" style={{
              background: `color-mix(in srgb, ${cert.color} 12%, transparent)`, color: cert.color,
            }}>{cert.label}</span>
          )}

          {editable ? (
            <input className="bz-cell-input bz-stage-date" type="date" title="처리기한"
                   value={stage.deadline || ''} disabled={!canEdit}
                   onChange={e => patch(stage, { deadline: e.target.value || null })} />
          ) : dday ? <span className="bz-stage-dday">{dday}</span> : null}

          {canEdit && editable && (
            <span className="bz-stage-admin">
              <button className="btn-ghost" title="위로"
                      onClick={() => move(group, idx, -1)}><ArrowUp size={12} /></button>
              <button className="btn-ghost" title="아래로"
                      onClick={() => move(group, idx, 1)}><ArrowDown size={12} /></button>
              <button className="btn-ghost" title="삭제"
                      onClick={() => removeStage(stage)}><Trash2 size={12} /></button>
            </span>
          )}
        </div>
      </div>
    )
  }

  const group = (title: string, list: PermitStage[],
                 category: 'statutory' | 'individual', editable: boolean) => (
    <div className="bz-stage-group">
      <div className="bz-block-title bz-stage-group-head">
        <span>{title}</span>
        {canEdit && editable && (
          <button className="btn-ghost bz-edit-btn" disabled={busy}
                  onClick={() => addStage(category)}><Plus size={13} /> 항목 추가</button>
        )}
      </div>
      {list.length === 0
        ? <p className="note">항목이 없습니다.</p>
        : list.map((s, i) => stageRow(s, list, i, editable))}
    </div>
  )

  const statutory = stages.filter(s => s.category === 'statutory')
  const individual = stages.filter(s => s.category === 'individual')
  const target = stages.filter(s => s.status !== 'na')
  const doneCount = target.filter(s => s.status === 'done').length

  const body = (editable: boolean) => (
    <>
      {group('3-1. 전기사업법 · 국토계획법 절차', statutory, 'statutory', editable)}
      {group('3-2. 개별법 협의', individual, 'individual', editable)}
    </>
  )

  return (
    <div className="card block">
      <SectionHead title="인허가 현황" updatedAt={lastEdited(stages.map(s => s.updated_at))}
                   canEdit={canEdit} onEdit={() => setEditing(true)}
                   extra={
                     <span className="bz-chip"
                           style={{ background: 'var(--mint-soft)', color: 'var(--green-600)' }}>
                       완료 {doneCount} / {target.length}
                     </span>
                   } />
      <input ref={fileInput} type="file" style={{ display: 'none' }}
             onChange={e => upload(e.target.files?.[0])} />
      <PipelineStrip stages={stages} />
      {body(false)}

      {editing && (
        <SectionModal title="인허가 현황"
                      hint="항목명·기관·내용·현황·확정도·특이사항·처리기한을 고치고, 문서 버전과 항목 순서를 관리합니다"
                      onClose={() => { setEditing(false); onChanged() }}>
          {body(true)}
        </SectionModal>
      )}
    </div>
  )
}
