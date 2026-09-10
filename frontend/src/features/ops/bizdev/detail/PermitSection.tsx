import { useRef, useState } from 'react'
import { ArrowDown, ArrowUp, Download, History, Plus, Trash2, Upload } from 'lucide-react'
import { apiSend, apiUpload } from '../api'
import { CERTAINTY_META, ddayLabel, STATUS_META } from '../constants'
import { CertaintyCell, EditableSelect, EditableText } from './editors'
import SectionModal from './SectionModal'
import SectionHead, { lastEdited } from './SectionHead'
import PipelineStrip from './PipelineStrip'
import Lines from './Lines'
import StageContent from './StageContent'
import type { PermitStage } from '../types'

const STATE_OPTIONS: Array<[string, string]> = [
  ['done', '완료'], ['active', '진행중'], ['idle', '미착수'], ['na', '미대상'],
]
// 원본(project.page.js ST)의 상태 글리프
const GLYPH: Record<string, string> = { done: '✓', active: '◐', idle: '·', na: '—' }
// 인허가 현황 — 원본 '인허가 상세 진척도' 카드 배치에 사업개요 양식의
// 내용·확정도·특이사항을 얹었다. 상·하위 묶음은 원본과 같이 tier + 줄 순서로 정한다.
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

  // 순서 이동 — 전체 목록에서 바로 위·아래 항목과 자리를 바꾼다.
  // 상위 항목을 지나치면 소속 묶음이 바뀌므로 이동만으로 계층을 조정할 수 있다.
  const move = async (stage: PermitStage, dir: -1 | 1) => {
    const ids = [...stages].sort((a, b) => a.stage_no - b.stage_no).map(s => s.id)
    const from = ids.indexOf(stage.id)
    const to = from + dir
    if (to < 0 || to >= ids.length) return
    ;[ids[from], ids[to]] = [ids[to], ids[from]]
    try {
      await apiSend('POST', '/api/bizdev/stages/reorder/', { site: siteId, ordered_ids: ids })
      onChanged()
    } catch (e) { fail(e, '순서 변경 실패') }
  }

  const addStage = async (tier: 'major' | 'minor') => {
    setBusy(true)
    try {
      await apiSend('POST', '/api/bizdev/stages/', {
        site: siteId, name: '새 항목', tier, agency: '', status: 'idle',
        certainty: 'unconfirmed', doc_label: '문서',
        category: tier === 'major' ? 'statutory' : 'individual',
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
  const stageRow = (stage: PermitStage, editable: boolean) => {
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

          <StageContent stage={stage} editable={editable} canEdit={canEdit}
                        onSave={v => patch(stage, { content: v })} />

          <div className="bz-stage-remark">
            <span className="bz-stage-tag">특이사항</span>
            {editable
              ? <EditableText value={stage.remark} multiline disabled={!canEdit} placeholder="—"
                              onSave={v => patch(stage, { remark: v })} />
              : <Lines text={stage.remark} />}
          </div>

          {(stage.documents.length > 0 || (canEdit && editable)) && (
            <div className="bz-stage-docs">
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
          )}

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

          {current ? (
            <a className="btn-ghost bz-doc-btn" target="_blank" rel="noreferrer"
               href={`/api/bizdev/documents/${current.id}/download/`}>
              <Download size={12} /> {stage.doc_label || '문서'} v{current.version}
            </a>
          ) : <span className="bz-doc-none">미취득</span>}

          {editable ? (
            <input className="bz-cell-input bz-stage-date" type="date" title="처리기한"
                   value={stage.deadline || ''} disabled={!canEdit}
                   onChange={e => patch(stage, { deadline: e.target.value || null })} />
          ) : dday ? <span className="bz-stage-dday">{dday}</span> : null}

          {canEdit && editable && (
            <EditableSelect value={stage.tier} disabled={!canEdit}
                            options={[['major', '상위'], ['minor', '하위']]}
                            onSave={v => patch(stage, {
                              tier: v, category: v === 'major' ? 'statutory' : 'individual',
                            })}
                            style={{ fontSize: 11, width: 68, textAlign: 'center' }} />
          )}

          {canEdit && editable && (
            <span className="bz-stage-admin">
              <button className="btn-ghost" title="위로"
                      onClick={() => move(stage, -1)}><ArrowUp size={12} /></button>
              <button className="btn-ghost" title="아래로"
                      onClick={() => move(stage, 1)}><ArrowDown size={12} /></button>
              <button className="btn-ghost" title="삭제"
                      onClick={() => removeStage(stage)}><Trash2 size={12} /></button>
            </span>
          )}
        </div>
      </div>
    )
  }

  // 묶기 — 원본 renderStages 와 같다. 줄 순서대로 읽다가 상위(major)를 만나면
  // 새 묶음을 열고, 뒤따르는 하위(minor)를 그 묶음에 담는다. 부모를 가리키는
  // 필드가 따로 없고 줄 순서가 곧 소속이라, ▲▼ 이동만으로 계층이 바뀐다.
  const ordered = [...stages].sort((a, b) => a.stage_no - b.stage_no)
  const groups: Array<{ head: PermitStage | null; items: PermitStage[] }> = []
  ordered.forEach(st => {
    const cur = groups[groups.length - 1]
    if (st.tier === 'major' || !cur) {
      groups.push(st.tier === 'major' ? { head: st, items: [] } : { head: null, items: [st] })
    } else {
      cur.items.push(st)
    }
  })

  const target = stages.filter(s => s.status !== 'na')
  const doneCount = target.filter(s => s.status === 'done').length

  const addBtn = (label: string, tier: 'major' | 'minor') => (
    <button className="btn-ghost bz-edit-btn" disabled={busy}
            onClick={() => addStage(tier)}><Plus size={13} /> {label}</button>
  )

  const body = (editable: boolean) => (
    <div className="bz-stage-list">
      {ordered.length === 0 && <p className="note">항목이 없습니다.</p>}
      {groups.map((g, gi) => (
        <div className="bz-stage-group" key={g.head?.id || g.items[0]?.id || gi}>
          {g.head && stageRow(g.head, editable)}
          {g.items.length > 0 && (
            <div className="bz-substages">
              {g.items.map(st => stageRow(st, editable))}
            </div>
          )}
        </div>
      ))}
      {canEdit && editable && (
        <div className="bz-stage-add">
          {addBtn('상위 항목 추가', 'major')}
          {addBtn('하위 항목 추가', 'minor')}
        </div>
      )}
    </div>
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
      <div className="bz-scroll bz-scroll-permit">{body(false)}</div>

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
