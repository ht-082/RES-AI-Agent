import { useRef, useState } from 'react'
import { Download, Plus, Trash2, Upload } from 'lucide-react'
import { apiSend, apiUpload } from '../api'
import SectionHead, { lastEdited } from './SectionHead'
import SectionModal from './SectionModal'
import { EditableText } from './editors'
import type { SiteDoc } from '../types'

// 문서 보관함 — 양식 §3. 인허가 문서는 인허가 카드가 따로 들고 있고,
// 여기에는 운영·법인·재무 문서를 모은다(인허가 분류도 필요하면 쓸 수 있다).
const CATEGORIES: Array<[string, string]> = [
  ['ops', '운영'], ['corp', '법인문서'], ['permit', '인허가'], ['fin', '재무'],
]
const HINT: Record<string, string> = {
  ops: '관리운영보고서 · Event Report',
  corp: '등기부등본 · 사업자등록증',
  permit: '발전사업허가증 · 개발행위허가증 · 최초 전력거래 확인서 · 준공필증',
  fin: '감사보고서',
}

export default function DocumentVault({ siteId, docs, canEdit, onChanged, onError, id }: {
  siteId: string
  docs: SiteDoc[]
  canEdit: boolean
  onChanged: () => void
  onError: (msg: string) => void
  id?: string
}) {
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)
  const target = useRef<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const fail = (e: unknown, fb: string) => onError(e instanceof Error ? e.message : fb)

  const patch = async (row: SiteDoc, body: Record<string, unknown>) => {
    await apiSend('PATCH', `/api/bizdev/site-documents/${row.id}/`, body)
    onChanged()
  }
  const add = async (category: string) => {
    setBusy(true)
    try {
      await apiSend('POST', '/api/bizdev/site-documents/', {
        site: siteId, category, title: '새 문서',
      })
      onChanged()
    } catch (e) { fail(e, '추가 실패') } finally { setBusy(false) }
  }
  const remove = async (row: SiteDoc) => {
    if (!confirm(`"${row.title}" 을(를) 삭제할까요? 첨부 파일도 함께 지워집니다.`)) return
    try {
      await apiSend('DELETE', `/api/bizdev/site-documents/${row.id}/`)
      onChanged()
    } catch (e) { fail(e, '삭제 실패') }
  }
  const upload = async (file: File | undefined) => {
    const docId = target.current
    if (!file || !docId) return
    const form = new FormData()
    form.append('file', file)
    try {
      await apiUpload(`/api/bizdev/site-documents/${docId}/`, form, 'PATCH')
      onChanged()
    } catch (e) { fail(e, '업로드 실패') }
    if (fileInput.current) fileInput.current.value = ''
  }

  const group = (key: string, label: string, editable: boolean) => {
    const rows = docs.filter(d => d.category === key)
    return (
      <div key={key} className="bz-vault-group">
        <div className="bz-block-title" style={{ justifyContent: 'space-between' }}>
          <span>{label}</span>
          {canEdit && editable && (
            <button className="btn-ghost bz-edit-btn" disabled={busy} onClick={() => add(key)}>
              <Plus size={13} /> 문서 추가
            </button>
          )}
        </div>
        {rows.length === 0 ? (
          <p className="note bz-vault-hint">{HINT[key]}</p>
        ) : (
          <table className="tbl bz-doc-tbl bz-vault-tbl">
            <thead>
              <tr>
                <th>문서</th>
                <th>일자</th>
                <th>파일</th>
                {canEdit && editable && <th className="bz-col-act" />}
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.id}>
                  <td title={row.title}>
                    {editable
                      ? <EditableText value={row.title} disabled={!canEdit} placeholder="문서 이름"
                                      onSave={v => patch(row, { title: v })} />
                      : row.title}
                  </td>
                  <td className="bz-nowrap">
                    {editable
                      ? <input className="bz-cell-input" type="date" value={row.doc_date || ''}
                               disabled={!canEdit}
                               onChange={e => patch(row, { doc_date: e.target.value || null })} />
                      : (row.doc_date || <span className="bz-muted">—</span>)}
                  </td>
                  <td>
                    {row.has_file ? (
                      <a className="btn-ghost bz-doc-btn" target="_blank" rel="noreferrer"
                         href={`/api/bizdev/site-documents/${row.id}/download/`}
                         title={row.file_name}>
                        <Download size={12} /> 받기
                      </a>
                    ) : <span className="bz-doc-none">파일 없음</span>}
                    {canEdit && editable && (
                      <button className="btn-ghost bz-doc-btn"
                              onClick={() => { target.current = row.id; fileInput.current?.click() }}>
                        <Upload size={12} /> {row.has_file ? '교체' : '올리기'}
                      </button>
                    )}
                  </td>
                  {canEdit && editable && (
                    <td>
                      <button className="btn-ghost" style={{ padding: 3 }} onClick={() => remove(row)}
                              aria-label="삭제"><Trash2 size={13} /></button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    )
  }

  const body = (editable: boolean) => (
    <>{CATEGORIES.map(([k, label]) => group(k, label, editable))}</>
  )

  return (
    <div className="card block" id={id}>
      <SectionHead title="문서 보관함" updatedAt={lastEdited(docs.map(d => d.updated_at))}
                   canEdit={canEdit} onEdit={() => setEditing(true)}
                   extra={<span className="bz-chip"
                                style={{ background: 'var(--mint-soft)', color: 'var(--green-600)' }}>
                            {docs.length}건
                          </span>} />
      <input ref={fileInput} type="file" style={{ display: 'none' }}
             onChange={e => upload(e.target.files?.[0])} />
      <div className="bz-scroll bz-scroll-permit">{body(false)}</div>

      {editing && (
        <SectionModal title="문서 보관함" hint="분류별로 문서를 두고 파일을 올립니다"
                      onClose={() => { setEditing(false); onChanged() }}>
          {body(true)}
        </SectionModal>
      )}
    </div>
  )
}
