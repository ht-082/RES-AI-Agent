import { useState } from 'react'
import { Download, TrendingUp, AlertTriangle, Info } from 'lucide-react'

type FinanceTab = 'generate' | 'review'

export default function FinanceView() {
  const [activeTab, setActiveTab] = useState<FinanceTab>('generate')

  return (
    <section style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
      <div className="tabs">
        <button className={`tab ${activeTab === 'generate' ? 'active' : ''}`} onClick={() => setActiveTab('generate')}>재무모델 생성</button>
        <button className={`tab ${activeTab === 'review' ? 'active' : ''}`} onClick={() => setActiveTab('review')}>재무모델 검토</button>
      </div>

      {activeTab === 'generate' && <GeneratePane />}
      {activeTab === 'review' && <ReviewPane />}
    </section>
  )
}

function GeneratePane() {
  return (
    <div className="pane">
      <div className="section-head">
        <h2>재무모델 생성</h2>
        <p>주요 가정사항을 입력하면 재무모델이 자동으로 생성됩니다. (PoC 버전: 항목 정의 및 화면 시안 반영)</p>
      </div>
      <div className="grid-2 lean">
        <div className="card block">
          <h3><span className="num">1</span>주요 가정사항</h3>
          <div className="h-sub">사업 가정을 입력하세요.</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label className="fld"><span className="lab">설비 용량</span><input className="inp" defaultValue="80 MW" /></label>
            <label className="fld"><span className="lab">이용률</span><input className="inp" defaultValue="15.8 %" /></label>
            <label className="fld"><span className="lab">총 사업비 (CAPEX)</span><input className="inp" defaultValue="1,120 억원" /></label>
            <label className="fld"><span className="lab">운영비 (OPEX)</span><input className="inp" defaultValue="연 28 억원" /></label>
            <label className="fld"><span className="lab">차입 비율</span><input className="inp" defaultValue="75 %" /></label>
            <label className="fld"><span className="lab">차입 금리</span><input className="inp" defaultValue="5.2 %" /></label>
            <label className="fld"><span className="lab">매출 단가</span><input className="inp" defaultValue="SMP+REC 165 원/kWh" /></label>
            <label className="fld"><span className="lab">사업 기간</span><input className="inp" defaultValue="20년" /></label>
          </div>
          <button className="btn-primary">
            <TrendingUp size={16} />
            재무모델 자동 생성
          </button>
        </div>

        <div className="card block">
          <div className="result-head">
            <div className="rh-l">생성 결과 <span className="badge">요약 지표</span></div>
            <button className="btn-ghost"><Download size={15} />Excel 다운로드</button>
          </div>
          <div className="metrics-grid" style={{ marginBottom: 18, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1, background: 'var(--line)', borderRadius: 12, overflow: 'hidden', border: '1px solid var(--line)' }}>
            <div className="metric" style={{ background: 'var(--surface)', padding: '16px 18px' }}>
              <div className="m-lab" style={{ fontSize: '11.5px', color: 'var(--ink-faint)', fontWeight: 600, marginBottom: 7 }}>Equity IRR</div>
              <div className="m-val" style={{ fontSize: '20px', fontWeight: 800 }}>8.7<span className="u" style={{ fontSize: 12, color: 'var(--ink-soft)' }}>%</span></div>
            </div>
            <div className="metric" style={{ background: 'var(--surface)', padding: '16px 18px' }}>
              <div className="m-lab" style={{ fontSize: '11.5px', color: 'var(--ink-faint)', fontWeight: 600, marginBottom: 7 }}>Project IRR</div>
              <div className="m-val" style={{ fontSize: '20px', fontWeight: 800 }}>6.4<span className="u" style={{ fontSize: 12, color: 'var(--ink-soft)' }}>%</span></div>
            </div>
            <div className="metric" style={{ background: 'var(--surface)', padding: '16px 18px' }}>
              <div className="m-lab" style={{ fontSize: '11.5px', color: 'var(--ink-faint)', fontWeight: 600, marginBottom: 7 }}>NPV</div>
              <div className="m-val" style={{ fontSize: '20px', fontWeight: 800 }}>142<span className="u" style={{ fontSize: 12, color: 'var(--ink-soft)' }}>억</span></div>
            </div>
            <div className="metric" style={{ background: 'var(--surface)', padding: '16px 18px' }}>
              <div className="m-lab" style={{ fontSize: '11.5px', color: 'var(--ink-faint)', fontWeight: 600, marginBottom: 7 }}>최소 DSCR</div>
              <div className="m-val" style={{ fontSize: '20px', fontWeight: 800 }}>1.28<span className="u" style={{ fontSize: 12, color: 'var(--ink-soft)' }}>x</span></div>
            </div>
            <div className="metric" style={{ background: 'var(--surface)', padding: '16px 18px' }}>
              <div className="m-lab" style={{ fontSize: '11.5px', color: 'var(--ink-faint)', fontWeight: 600, marginBottom: 7 }}>투자비 회수</div>
              <div className="m-val" style={{ fontSize: '20px', fontWeight: 800 }}>11.2<span className="u" style={{ fontSize: 12, color: 'var(--ink-soft)' }}>년</span></div>
            </div>
            <div className="metric" style={{ background: 'var(--surface)', padding: '16px 18px' }}>
              <div className="m-lab" style={{ fontSize: '11.5px', color: 'var(--ink-faint)', fontWeight: 600, marginBottom: 7 }}>LCOE</div>
              <div className="m-val" style={{ fontSize: '20px', fontWeight: 800 }}>138<span className="u" style={{ fontSize: 12, color: 'var(--ink-soft)' }}>원</span></div>
            </div>
          </div>
          <div className="chart-head" style={{ marginBottom: 10 }}><h3 style={{ fontSize: 13, fontWeight: 700 }}>연도별 잉여현금흐름 (FCF)</h3></div>
          <div className="bars" style={{ height: 130, display: 'flex', alignItems: 'flex-end', gap: 10, paddingTop: 10 }}>
            <div className="bar-col" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%', justifyContent: 'flex-end' }}>
              <div className="bar-stack" style={{ width: '100%', maxWidth: 34, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%', gap: 3 }}>
                <div className="bar actual" style={{ height: '22%', width: '100%', borderRadius: '5px 5px 0 0', background: 'linear-gradient(180deg,var(--green-accent),var(--brand))' }}></div>
              </div>
              <div className="bar-x" style={{ fontSize: 11, color: 'var(--ink-faint)', fontWeight: 600 }}>1Y</div>
            </div>
            <div className="bar-col" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%', justifyContent: 'flex-end' }}>
              <div className="bar-stack" style={{ width: '100%', maxWidth: 34, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%', gap: 3 }}>
                <div className="bar actual" style={{ height: '38%', width: '100%', borderRadius: '5px 5px 0 0', background: 'linear-gradient(180deg,var(--green-accent),var(--brand))' }}></div>
              </div>
              <div className="bar-x" style={{ fontSize: 11, color: 'var(--ink-faint)', fontWeight: 600 }}>4Y</div>
            </div>
            <div className="bar-col" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%', justifyContent: 'flex-end' }}>
              <div className="bar-stack" style={{ width: '100%', maxWidth: 34, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%', gap: 3 }}>
                <div className="bar actual" style={{ height: '52%', width: '100%', borderRadius: '5px 5px 0 0', background: 'linear-gradient(180deg,var(--green-accent),var(--brand))' }}></div>
              </div>
              <div className="bar-x" style={{ fontSize: 11, color: 'var(--ink-faint)', fontWeight: 600 }}>8Y</div>
            </div>
            <div className="bar-col" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%', justifyContent: 'flex-end' }}>
              <div className="bar-stack" style={{ width: '100%', maxWidth: 34, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%', gap: 3 }}>
                <div className="bar actual" style={{ height: '74%', width: '100%', borderRadius: '5px 5px 0 0', background: 'linear-gradient(180deg,var(--green-accent),var(--brand))' }}></div>
              </div>
              <div className="bar-x" style={{ fontSize: 11, color: 'var(--ink-faint)', fontWeight: 600 }}>12Y</div>
            </div>
            <div className="bar-col" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%', justifyContent: 'flex-end' }}>
              <div className="bar-stack" style={{ width: '100%', maxWidth: 34, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%', gap: 3 }}>
                <div className="bar actual" style={{ height: '88%', width: '100%', borderRadius: '5px 5px 0 0', background: 'linear-gradient(180deg,var(--green-accent),var(--brand))' }}></div>
              </div>
              <div className="bar-x" style={{ fontSize: 11, color: 'var(--ink-faint)', fontWeight: 600 }}>16Y</div>
            </div>
            <div className="bar-col" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%', justifyContent: 'flex-end' }}>
              <div className="bar-stack" style={{ width: '100%', maxWidth: 34, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%', gap: 3 }}>
                <div className="bar actual" style={{ height: '100%', width: '100%', borderRadius: '5px 5px 0 0', background: 'linear-gradient(180deg,var(--green-accent),var(--brand))' }}></div>
              </div>
              <div className="bar-x" style={{ fontSize: 11, color: 'var(--ink-faint)', fontWeight: 600 }}>20Y</div>
            </div>
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
        <h2>재무모델 검토</h2>
        <p>업로드한 재무모델의 수식 오류 등을 검토하고, 셀 위치·이상 내용·수정 방향을 표로 제시합니다. (PoC 버전: 항목 정의 및 화면 시안 반영)</p>
      </div>
      <div className="grid-2 lean">
        <div className="card block">
          <h3><span className="num">1</span>재무모델 업로드</h3>
          <div className="h-sub">Excel 파일을 올리세요.</div>
          <div className="drop">
            <div className="d-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" style={{ width: 22, height: 22, color: 'var(--green-accent)' }}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5M12 3v12"/></svg></div>
            <b>파일을 끌어다 놓거나 클릭하여 업로드</b>
            <span>Excel (.xlsx) · 최대 50MB</span>
          </div>
          <div className="file-pill">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" style={{ width: 16, height: 16 }}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
            새만금태양광_재무모델_v5.xlsx
            <span className="x">✕</span>
          </div>
          <button className="btn-primary" style={{ marginTop: 18 }}>
            <TrendingUp size={16} />
            수식 오류 검토
          </button>
          <div className="note" style={{ marginTop: 16 }}>
            <Info size={17} />
            순환참조, 하드코딩, 부호 오류, 시트 간 연결 끊김을 중점 점검합니다.
          </div>
        </div>

        <div className="card block">
          <div className="result-head">
            <div className="rh-l">검토 결과 <span className="badge">이상 4건 발견</span></div>
            <button className="btn-ghost"><Download size={15} />Excel 다운로드</button>
          </div>
          <table className="tbl">
            <thead>
              <tr><th>셀 위치</th><th>유형</th><th>이상 내용 · 수정 방향</th></tr>
            </thead>
            <tbody>
              <tr>
                <td><span className="cell-ref">CF!D24</span></td>
                <td><span className="sev high">오류</span></td>
                <td>차입 원리금 부호 반대 → 음수(-)로 수정 필요</td>
              </tr>
              <tr>
                <td><span className="cell-ref">Rev!F12</span></td>
                <td><span className="sev mid">하드코딩</span></td>
                <td>REC 단가 직접 입력 → 가정 시트 참조로 변경</td>
              </tr>
              <tr>
                <td><span className="cell-ref">Debt!H8</span></td>
                <td><span className="sev high">순환참조</span></td>
                <td>이자·잔액 상호참조 → 반복계산 또는 구조 분리</td>
              </tr>
              <tr>
                <td><span className="cell-ref">CF!M30</span></td>
                <td><span className="sev low">경고</span></td>
                <td>잔존가치 누락 → 사업 종료연도 반영 권장</td>
              </tr>
            </tbody>
          </table>
          <div className="note" style={{ marginTop: 16, background: 'var(--red-soft)', borderColor: '#F5C6CB', color: 'var(--red)' }}>
            <AlertTriangle size={17} style={{ color: 'var(--red)' }} />
            CF!D24의 부호 오류는 Equity IRR을 약 1.4%p 과대계상시키는 핵심 오류입니다.
          </div>
        </div>
      </div>
    </div>
  )
}
