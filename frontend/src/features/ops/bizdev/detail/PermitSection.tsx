import { Download, Upload } from 'lucide-react'
import { useRef } from 'react'
import { apiSend, apiUpload } from '../api'
import { STATUS_META } from '../constants'
import { CertaintyCell, EditableSelect, EditableText } from './editors'
import type { PermitStage } from '../types'

const STATE_OPTIONS: Array<[string, string]> = [
  ['done', '완료'], ['active', '진행중'], ['idle', '미착수'], ['na', '미대상'],
]

// 인허가 현황 — 양식 §3 (3-1 법정절차 / 3-2 개별법 협의)
export default function PermitSection({ stages, canEdit, onChanged, onError }: {
  stages: PermitStage[]
  canEdit: boolean
  onChanged: () => void
  onError: (msg: string) => void
}) {
  const uploadTarget = useRef<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const patch = async (stage: PermitStage, body: Partial<PermitStage>) => {
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
    } catch (e) {
      onError(e instanceof Error ? e.message : '업로드 실패')
    }
    if (fileInput.current) fileInput.current.value = ''
  }

  const table = (title: string, rows: PermitStage[]) => (
    <div style={{ marginTop: 14 }}>
      <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 6 }}>{title}</div>
      <table className="tbl bz-doc-tbl">
        <thead>
          <tr>
            <th style={{ width: 160 }}>구분</th>
            <th style={{ width: 88 }}>현황</th>
            <th>내용</th>
            <th style={{ width: 90 }}>확정도</th>
            <th>허가 · 협의 특이사항</th>
            <th style={{ width: 110 }}>문서</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(st => {
            const current = st.documents.find(d => d.is_current)
            return (
              <tr key={st.id}>
                <td>
                  <div style={{ fontWeight: 600 }}>{st.name}</div>
                  {st.agency && (
                    <div style={{ fontSize: 10.5, color: 'var(--ink-faint)' }}>{st.agency}</div>
                  )}
                </td>
                <td>
                  <EditableSelect
                    value={st.status} options={STATE_OPTIONS} disabled={!canEdit}
                    onSave={v => patch(st, { status: v as PermitStage['status'] })}
                    style={{
                      color: STATUS_META[st.status].color, fontWeight: 700, fontSize: 11,
                      background: `color-mix(in srgb, ${STATUS_META[st.status].color} 12%, transparent)`,
                      borderRadius: 6, textAlign: 'center', width: 76,
                    }} />
                </td>
                <td>
                  <EditableText value={st.content} multiline disabled={!canEdit}
                                onSave={v => patch(st, { content: v })} />
                </td>
                <td>
                  <CertaintyCell value={st.certainty} disabled={!canEdit}
                                 onSave={v => patch(st, { certainty: v as PermitStage['certainty'] })} />
                </td>
                <td>
                  <EditableText value={st.remark} multiline placeholder="—" disabled={!canEdit}
                                onSave={v => patch(st, { remark: v })} />
                </td>
                <td>
                  {current ? (
                    <a className="btn-ghost" style={{ fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 3, textDecoration: 'none' }}
                       href={`/api/bizdev/documents/${current.id}/download/`} target="_blank" rel="noreferrer">
                      <Download size={12} /> v{current.version}
                    </a>
                  ) : (
                    <span style={{ fontSize: 11, color: 'var(--ink-faint)' }}>—</span>
                  )}
                  {canEdit && (
                    <button className="btn-ghost" style={{ padding: 4 }} title={`${st.doc_label} 업로드`}
                            onClick={() => { uploadTarget.current = st.id; fileInput.current?.click() }}>
                      <Upload size={12} />
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )

  const statutory = stages.filter(s => s.category === 'statutory')
  const individual = stages.filter(s => s.category === 'individual')
  const target = stages.filter(s => s.status !== 'na')
  const doneCount = target.filter(s => s.status === 'done').length

  return (
    <div className="card block">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h3>3. 인허가 현황</h3>
        <span className="bz-chip" style={{ background: 'var(--mint-soft)', color: 'var(--green-600)' }}>
          완료 {doneCount} / {target.length}
        </span>
      </div>
      <div className="h-sub">현황·내용·확정도·특이사항을 표에서 바로 고칠 수 있습니다</div>
      <input ref={fileInput} type="file" style={{ display: 'none' }}
             onChange={e => upload(e.target.files?.[0])} />
      {table('3-1. 전기사업법 · 국토계획법 절차', statutory)}
      {table('3-2. 개별법 협의', individual)}
    </div>
  )
}
