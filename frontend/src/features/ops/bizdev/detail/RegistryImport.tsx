import { useRef, useState } from 'react'
import { FileUp } from 'lucide-react'
import { apiUpload } from '../api'

interface Filled { label: string; before: string; after: string }

// 법인등기부등본(PDF)을 올려 SPC 항목을 자동으로 채운다.
// 인터넷등기소 PDF 는 텍스트라 OCR 없이 읽힌다 — 스캔본이면 서버가 알려 준다.
export default function RegistryImport({ siteId, onDone }: {
  siteId: string
  onDone: () => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<Filled[] | null>(null)
  const [error, setError] = useState('')

  const upload = async (file: File | undefined) => {
    if (!file) return
    setBusy(true); setError(''); setResult(null)
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await apiUpload<{ filled: Filled[]; found: number }>(
        `/api/bizdev/sites/${siteId}/import-registry/`, form)
      setResult(res.filled)
      onDone()
    } catch (e) {
      setError(e instanceof Error ? e.message : '읽지 못했습니다.')
    } finally {
      setBusy(false)
      if (input.current) input.current.value = ''
    }
  }

  return (
    <div className="bz-registry">
      <div className="bz-inline" style={{ justifyContent: 'space-between' }}>
        <span className="bz-hint" style={{ marginTop: 0 }}>
          법인등기부등본(PDF)을 올리면 회사명·법인등록번호·본점·자본금·이사진·설립일을 채웁니다
        </span>
        <button className="btn-ghost bz-edit-btn" disabled={busy}
                onClick={() => input.current?.click()}>
          <FileUp size={13} /> {busy ? '읽는 중...' : '등기부등본 올리기'}
        </button>
      </div>
      <input ref={input} type="file" accept="application/pdf" style={{ display: 'none' }}
             onChange={e => upload(e.target.files?.[0])} />

      {error && <p className="note" style={{ color: 'var(--red)', marginTop: 6 }}>{error}</p>}
      {result && (
        <div style={{ marginTop: 8 }}>
          {result.length === 0 ? (
            <p className="note">이미 등본과 같은 값입니다 — 바뀐 항목이 없습니다.</p>
          ) : (
            <>
              <div className="bz-hint">{result.length}개 항목을 채웠습니다</div>
              {result.map(f => (
                <div key={f.label} className="bz-registry-row">
                  <span className="bz-registry-label">{f.label}</span>
                  <span className="bz-muted">{f.before || '(빈칸)'}</span>
                  <span>→</span>
                  <span style={{ fontWeight: 600 }}>{f.after.split('\n')[0]}</span>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}
