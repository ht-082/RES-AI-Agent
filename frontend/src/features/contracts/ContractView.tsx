import { useState, useEffect } from 'react'
import { Download, CheckSquare, Upload, Info, Loader2, Sparkles, AlertCircle } from 'lucide-react'

type ContractTab = 'generate' | 'review'

interface FieldSchema {
  key: string
  label: string
  input: 'text' | 'textarea' | 'select'
  required?: boolean
  placeholder?: string
  options?: string[]
}

interface ContractType {
  type_id: string
  type_name: string
  fields: FieldSchema[]
  article_structure: string[]
}

interface Article {
  no: string
  heading: string | null
  content: string
}

interface GeneratedDraft {
  draft_id: string
  title: string
  articles: Article[]
  mapping_note: string
}

export default function ContractView() {
  const [activeTab, setActiveTab] = useState<ContractTab>('generate')

  return (
    <section style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', padding: '16px 24px' }}>
      <div className="tabs" style={{ marginBottom: 20 }}>
        <button 
          className={`tab ${activeTab === 'generate' ? 'active' : ''}`} 
          onClick={() => setActiveTab('generate')}
        >
          계약서 신규 생성
        </button>
        <button 
          className={`tab ${activeTab === 'review' ? 'active' : ''}`} 
          onClick={() => setActiveTab('review')}
        >
          계약서 검토
        </button>
      </div>

      {activeTab === 'generate' && <GeneratePane />}
      {activeTab === 'review' && <ReviewPane />}
    </section>
  )
}

function GeneratePane() {
  const [contractTypes, setContractTypes] = useState<ContractType[]>([])
  const [selectedTypeId, setSelectedTypeId] = useState<string>('')
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [generating, setGenerating] = useState(false)
  const [generatedDraft, setGeneratedDraft] = useState<GeneratedDraft | null>(null)
  
  const [loadingTypes, setLoadingTypes] = useState(true)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // 1. 계약서 유형 목록 로딩 (GET /api/contract/types)
  useEffect(() => {
    async function fetchTypes() {
      try {
        const res = await fetch('/api/contract/types', { credentials: 'include' })
        if (!res.ok) throw new Error('계약 유형 목록을 불러오는 데 실패했습니다.')
        const data = await res.json()
        setContractTypes(data)
        
        if (data && data.length > 0) {
          setSelectedTypeId(data[0].type_id)
          // 첫 번째 유형 필드로 입력 상태 초기화
          const initialInputs: Record<string, string> = {}
          data[0].fields.forEach((f: FieldSchema) => {
            initialInputs[f.key] = ''
          })
          setInputs(initialInputs)
        }
      } catch (err: any) {
        console.error(err)
        setErrorMsg(err.message || '서버 통신 오류가 발생했습니다.')
      } finally {
        setLoadingTypes(false)
      }
    }
    fetchTypes()
  }, [])

  // 계약 유형 셀렉트 박스 변경 핸들러
  const handleTypeChange = (typeId: string) => {
    setSelectedTypeId(typeId)
    const targetType = contractTypes.find(t => t.type_id === typeId)
    if (targetType) {
      const resetInputs: Record<string, string> = {}
      targetType.fields.forEach(f => {
        resetInputs[f.key] = ''
      })
      setInputs(resetInputs)
    }
  }

  // 동적 필드 입력 값 핸들러
  const handleInputChange = (key: string, value: string) => {
    setInputs(prev => ({ ...prev, [key]: value }))
  }

  // 현재 선택된 유형 정보
  const selectedType = contractTypes.find(t => t.type_id === selectedTypeId)

  // 필수 필드 미입력 확인 (required 인데 값이 비어 있는 필드가 존재하는가?)
  const incompleteFields = selectedType?.fields.filter(
    f => f.required && (!inputs[f.key] || inputs[f.key].trim() === '')
  ) || []
  
  const isGenerateDisabled = incompleteFields.length > 0 || generating

  // 2. 계약서 생성 처리 (POST /api/contract/generate)
  const handleGenerate = async () => {
    if (isGenerateDisabled) return
    setGenerating(true)
    setErrorMsg(null)
    setGeneratedDraft(null)

    try {
      // CSRF 토큰 취득
      const csrfRes = await fetch('/api/auth/csrf/', { credentials: 'include' })
      const csrfData = await csrfRes.json()

      const res = await fetch('/api/contract/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfData.csrfToken
        },
        body: JSON.stringify({
          type_id: selectedTypeId,
          inputs: inputs
        }),
        credentials: 'include'
      })

      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.error || '계약서 생성 요청 실패')
      }

      const data = await res.json()
      setGeneratedDraft(data)
    } catch (err: any) {
      console.error(err)
      setErrorMsg(err.message || '초안 생성에 실패했습니다. 다시 시도해 주세요.')
    } finally {
      setGenerating(false)
    }
  }

  if (loadingTypes) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '300px', gap: 12 }}>
        <Loader2 className="animate-spin" size={32} style={{ color: '#4f46e5' }} />
        <span style={{ color: '#666', fontSize: '14px' }}>계약 스키마 정보를 로드하고 있습니다...</span>
      </div>
    )
  }

  return (
    <div className="pane">
      <div className="section-head">
        <h2>계약서 신규 생성</h2>
        <p>핵심 조건(Key-term)을 입력하면 동적 템플릿과 LLM을 조합하여 완성형 초안을 생성합니다.</p>
      </div>

      <div className="grid-2 lean" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', alignItems: 'start' }}>
        
        {/* 좌측 카드: 조건 입력 */}
        <div className="card block" style={{ padding: '24px', backgroundColor: '#fff', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '18px', fontWeight: 'bold', margin: '0 0 16px 0' }}>
            <span className="num" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '24px', height: '24px', borderRadius: '50%', backgroundColor: '#4f46e5', color: '#fff', fontSize: '12px', fontWeight: 'bold' }}>1</span>
            핵심 조건 입력
          </h3>
          <div className="h-sub" style={{ color: '#666', fontSize: '13px', marginBottom: '20px' }}>계약서 종류와 필수/선택 주요 key-term을 설정해 주세요.</div>
          
          {/* 계약 유형 셀렉트 박스 */}
          <label className="fld" style={{ display: 'block', marginBottom: '16px' }}>
            <span className="lab" style={{ display: 'block', fontSize: '13px', fontWeight: '600', color: '#374151', marginBottom: '6px' }}>계약 유형</span>
            <select 
              className="inp" 
              value={selectedTypeId} 
              onChange={e => handleTypeChange(e.target.value)}
              style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '14px' }}
            >
              {contractTypes.map(t => (
                <option key={t.type_id} value={t.type_id}>{t.type_name}</option>
              ))}
            </select>
          </label>

          {/* 동적 fields 생성 */}
          {selectedType?.fields.map(field => (
            <label className="fld" key={field.key} style={{ display: 'block', marginBottom: '16px' }}>
              <span className="lab" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '13px', fontWeight: '600', color: '#374151', marginBottom: '6px' }}>
                {field.label}
                {field.required && <span style={{ color: '#ef4444' }}>*</span>}
              </span>

              {field.input === 'text' && (
                <input 
                  type="text"
                  className="inp"
                  placeholder={field.placeholder || `${field.label}을(를) 입력해 주세요.`}
                  value={inputs[field.key] || ''}
                  onChange={e => handleInputChange(field.key, e.target.value)}
                  style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '14px' }}
                />
              )}

              {field.input === 'textarea' && (
                <textarea 
                  className="inp"
                  placeholder={field.placeholder || `${field.label} 조건을 자유롭게 입력하세요.`}
                  value={inputs[field.key] || ''}
                  onChange={e => handleInputChange(field.key, e.target.value)}
                  style={{ width: '100%', minHeight: '90px', padding: '10px 12px', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '14px', resize: 'vertical' }}
                />
              )}

              {field.input === 'select' && (
                <select
                  className="inp"
                  value={inputs[field.key] || ''}
                  onChange={e => handleInputChange(field.key, e.target.value)}
                  style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '14px' }}
                >
                  <option value="">선택해 주세요</option>
                  {field.options?.map(opt => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              )}
            </label>
          ))}

          {/* 에러 발생 안내 박스 */}
          {errorMsg && (
            <div style={{ padding: '12px', borderRadius: '6px', backgroundColor: '#fef2f2', border: '1px solid #fee2e2', color: '#ef4444', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <AlertCircle size={16} />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* 필수 미작성 알림 */}
          {incompleteFields.length > 0 && (
            <div style={{ color: '#ef4444', fontSize: '12.5px', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <AlertCircle size={14} />
              <span>필수 입력 항목(*표시)을 작성해야 생성 단추가 활성화됩니다.</span>
            </div>
          )}

          {/* 초안 생성 버튼 */}
          <button 
            className="btn-primary" 
            disabled={isGenerateDisabled}
            onClick={handleGenerate}
            style={{ 
              width: '100%', 
              padding: '12px', 
              borderRadius: '6px', 
              backgroundColor: isGenerateDisabled ? '#9ca3af' : '#4f46e5', 
              color: '#fff', 
              border: 'none', 
              fontWeight: '600', 
              fontSize: '14px', 
              cursor: isGenerateDisabled ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              transition: 'background-color 0.2s'
            }}
          >
            {generating ? (
              <>
                <Loader2 className="animate-spin" size={16} />
                계약 초안 작성 중...
              </>
            ) : (
              <>
                <Sparkles size={16} />
                계약서 초안 생성
              </>
            )}
          </button>
        </div>

        {/* 우측 카드: 초안 미리보기 */}
        <div className="card block" style={{ padding: '24px', backgroundColor: '#fff', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)', minHeight: '450px', display: 'flex', flexDirection: 'column' }}>
          <div className="result-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #f3f4f6', paddingBottom: '14px', marginBottom: '16px' }}>
            <div className="rh-l" style={{ fontSize: '16px', fontWeight: 'bold', color: '#111827' }}>
              생성된 초안 <span className="badge" style={{ padding: '3px 8px', borderRadius: '12px', backgroundColor: '#e0e7ff', color: '#4f46e5', fontSize: '11px', fontWeight: '600', marginLeft: '6px' }}>미리보기</span>
            </div>
            
            <button 
              className="btn-ghost"
              disabled={!generatedDraft}
              onClick={() => {
                if (generatedDraft) {
                  window.open(`/api/contract/drafts/${generatedDraft.draft_id}/download`, '_blank');
                }
              }}
              style={{ 
                padding: '6px 12px', 
                borderRadius: '6px', 
                border: '1px solid #e5e7eb', 
                backgroundColor: '#fff', 
                fontSize: '13px', 
                fontWeight: '500', 
                color: generatedDraft ? '#374151' : '#9ca3af',
                cursor: generatedDraft ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <Download size={14} />
              Word 다운로드
            </button>
          </div>

          {/* 본문 미리보기 구역 */}
          {generating ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px', color: '#4f46e5' }}>
              <Loader2 className="animate-spin" size={32} />
              <div style={{ fontSize: '14px', fontWeight: '600', color: '#4f46e5' }}>AI가 계약 조항을 정밀 조립하고 있습니다...</div>
              <div style={{ fontSize: '12px', color: '#888' }}>설정된 조항 순서에 따라 초안을 생성 중입니다.</div>
            </div>
          ) : generatedDraft ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="doc-preview" style={{ maxHeight: '420px', overflowY: 'auto', padding: '16px', backgroundColor: '#f9fafb', borderRadius: '8px', border: '1px solid #f3f4f6' }}>
                <h4 style={{ fontSize: '16px', fontWeight: '8xl', color: '#111827', textAlign: 'center', marginBottom: '20px', borderBottom: '2px solid #e5e7eb', paddingBottom: '10px' }}>
                  {generatedDraft.title}
                </h4>
                
                {generatedDraft.articles?.map((art, idx) => (
                  <div key={idx} style={{ marginBottom: '18px' }}>
                    <h5 style={{ fontSize: '14px', fontWeight: '700', color: '#1f2937', margin: '0 0 6px 0' }}>
                      {art.no} {art.heading ? `(${art.heading})` : ''}
                    </h5>
                    <blockquote className="clause-quote" style={{ margin: '0', paddingLeft: '12px', borderLeft: '3px solid #cbd5e1', color: '#4b5563', fontSize: '13.5px', lineHeight: '1.6', textAlign: 'justify' }}>
                      {art.content}
                    </blockquote>
                  </div>
                ))}
              </div>

              {/* mapping_note 하단 표시 박스 */}
              {generatedDraft.mapping_note && (
                <div className="note" style={{ padding: '12px 16px', borderRadius: '8px', backgroundColor: '#ecfdf5', border: '1px solid #d1fae5', color: '#065f46', fontSize: '13px', display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                  <Info size={18} style={{ color: '#059669', flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <strong style={{ display: 'block', marginBottom: '4px' }}>입력한 Key-term은 표준 PPA 양식의 해당 조항에 자동 매핑되었습니다.</strong>
                    <span style={{ color: '#047857', fontSize: '12.5px' }}>{generatedDraft.mapping_note}</span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', gap: '8px' }}>
              <Info size={28} style={{ color: '#d1d5db' }} />
              <div style={{ fontSize: '14px', fontWeight: '500' }}>좌측에 조건을 입력하고 초안을 생성하세요.</div>
            </div>
          )}

          {/* 하단 고정 면책 문구 */}
          <div style={{ marginTop: 'auto', paddingTop: '14px', borderTop: '1px solid #f3f4f6', color: '#9ca3af', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span>※ 본 초안은 참고용이며, 최종 계약은 법무 검토가 필요합니다.</span>
          </div>
        </div>

      </div>
    </div>
  )
}

function ReviewPane() {
  return (
    <div className="pane">
      <div className="section-head">
        <h2>계약서 검토</h2>
        <p>검토 중인 계약서 또는 Key-term을 업로드하면, 지시에 따라 조항별 검토 의견을 제시합니다.</p>
      </div>
      <div className="grid-2 lean" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        <div className="card block" style={{ padding: '24px', backgroundColor: '#fff', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '18px', fontWeight: 'bold', margin: '0 0 16px 0' }}>
            <span className="num" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '24px', height: '24px', borderRadius: '50%', backgroundColor: '#4f46e5', color: '#fff', fontSize: '12px', fontWeight: 'bold' }}>1</span>
            검토 대상 업로드
          </h3>
          <div className="h-sub" style={{ color: '#666', fontSize: '13px', marginBottom: '20px' }}>PDF · Word 파일을 올리세요.</div>
          <div className="drop" style={{ border: '2px dashed #d1d5db', borderRadius: '8px', padding: '30px', textAlign: 'center', cursor: 'pointer', marginBottom: '16px' }}>
            <div className="d-ic" style={{ marginBottom: '10px', color: '#4f46e5' }}><Upload size={22} style={{ margin: '0 auto' }} /></div>
            <b>파일을 끌어다 놓거나 클릭하여 업로드</b>
            <span style={{ display: 'block', fontSize: '12px', color: '#888', marginTop: '6px' }}>PDF, Word · 최대 50MB</span>
          </div>
          <div className="file-pill" style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', backgroundColor: '#f3f4f6', borderRadius: '20px', width: 'fit-content', fontSize: '13px', color: '#374151' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" style={{ width: '14px', height: '14px' }}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
            EPC도급계약서_상대방초안.docx
            <span className="x" style={{ cursor: 'pointer', marginLeft: '6px', color: '#ef4444' }}>✕</span>
          </div>
          <label className="fld" style={{ display: 'block', marginTop: '18px' }}>
            <span className="lab" style={{ display: 'block', fontSize: '13px', fontWeight: '600', color: '#374151', marginBottom: '6px' }}>검토 지시</span>
            <textarea className="inp" placeholder="예: 우리가 매수인 입장일 때 불리한 조항을 찾아주고, 협상에서 관철할 수정안을 제시해줘" defaultValue="매수인 입장에서 불리한 조항을 찾고, 표준 양식 대비 누락·독소 조항을 표시해줘." style={{ width: '100%', minHeight: '80px', padding: '10px 12px', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '14px' }} />
          </label>
          <button className="btn-primary" style={{ width: '100%', padding: '12px', borderRadius: '6px', backgroundColor: '#4f46e5', color: '#fff', border: 'none', fontWeight: '600', fontSize: '14px', marginTop: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
            <CheckSquare size={16} />
            계약서 검토 실행
          </button>
        </div>

        <div className="card block" style={{ padding: '24px', backgroundColor: '#fff', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
          <div className="result-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #f3f4f6', paddingBottom: '14px', marginBottom: '16px' }}>
            <div className="rh-l" style={{ fontSize: '16px', fontWeight: 'bold', color: '#111827' }}>검토 결과 <span className="badge" style={{ padding: '3px 8px', borderRadius: '12px', backgroundColor: '#fee2e2', color: '#ef4444', fontSize: '11px', fontWeight: '600', marginLeft: '6px' }}>조항 3건 지적</span></div>
            <button className="btn-ghost" style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #e5e7eb', backgroundColor: '#fff', fontSize: '13px', fontWeight: '500', color: '#374151', display: 'flex', alignItems: 'center', gap: '6px' }}><Download size={15} />Word 다운로드</button>
          </div>
          <table className="tbl" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #e5e7eb' }}><th style={{ padding: '8px 4px', fontWeight: '600', color: '#4b5563' }}>조항</th><th style={{ padding: '8px 4px', fontWeight: '600', color: '#4b5563' }}>위험도</th><th style={{ padding: '8px 4px', fontWeight: '600', color: '#4b5563' }}>지적 내용 · 수정 방향</th></tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: '10px 4px' }}><span className="cell-ref" style={{ fontFamily: 'monospace', padding: '2px 4px', backgroundColor: '#f3f4f6', borderRadius: '4px' }}>제12조</span></td>
                <td style={{ padding: '10px 4px' }}><span className="sev high" style={{ padding: '3px 8px', borderRadius: '12px', backgroundColor: '#fee2e2', color: '#ef4444', fontSize: '11px', fontWeight: '600' }}>독소</span></td>
                <td style={{ padding: '10px 4px', color: '#374151' }}>지체상금 상한 없음 → 계약금액의 10% 상한 신설 제안</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: '10px 4px' }}><span className="cell-ref" style={{ fontFamily: 'monospace', padding: '2px 4px', backgroundColor: '#f3f4f6', borderRadius: '4px' }}>제18조</span></td>
                <td style={{ padding: '10px 4px' }}><span className="sev mid" style={{ padding: '3px 8px', borderRadius: '12px', backgroundColor: '#fef3c7', color: '#d97706', fontSize: '11px', fontWeight: '600' }}>불리</span></td>
                <td style={{ padding: '10px 4px', color: '#374151' }}>하자담보 책임 5년 → 표준 2년 대비 과도, 단축 협상 필요</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: '10px 4px' }}><span className="cell-ref" style={{ fontFamily: 'monospace', padding: '2px 4px', backgroundColor: '#f3f4f6', borderRadius: '4px' }}>—</span></td>
                <td style={{ padding: '10px 4px' }}><span className="sev low" style={{ padding: '3px 8px', borderRadius: '12px', backgroundColor: '#e0f2fe', color: '#0284c7', fontSize: '11px', fontWeight: '600' }}>누락</span></td>
                <td style={{ padding: '10px 4px', color: '#374151' }}>불가항력 조항 부재 → 표준 양식 제24조 삽입 권장</td>
              </tr>
            </tbody>
          </table>
          <div className="note" style={{ marginTop: '16px', padding: '12px 16px', borderRadius: '8px', backgroundColor: '#eff6ff', border: '1px solid #dbeafe', color: '#1e40af', fontSize: '13px', display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
            <Info size={17} style={{ color: '#2563eb', flexShrink: 0, marginTop: '2px' }} />
            <span>과거 EPC 협상 사례 7건에서 동일 쟁점이 관철된 이력이 있어 협상 우선순위로 표시했습니다.</span>
          </div>
        </div>
      </div>
    </div>
  )
}
