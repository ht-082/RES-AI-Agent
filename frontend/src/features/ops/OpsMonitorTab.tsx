import { Activity, ShieldAlert, Cpu, Database } from 'lucide-react'

// 기존 OpsView 의 운영 현황 목업을 그대로 옮긴 탭 (PoC 시안)
export default function OpsMonitorTab() {
  return (
    <section className="pane" style={{ flex: 1, overflowY: 'auto' }}>
      <div className="section-head">
        <h2>운영 현황</h2>
        <p>발전 자산 현황 및 주요 운용 데이터를 실시간으로 모니터링합니다. (PoC 버전: UI 시안 기반 구현)</p>
      </div>

      {/* KPI Cards */}
      <div className="kpi-row">
        <div className="kpi">
          <div className="k-lab">
            <Cpu size={15} />
            총 설비용량
          </div>
          <div className="k-val">124.5<span className="u">MW</span></div>
          <div className="k-sub up">▲ 12% 전년대비</div>
        </div>
        <div className="kpi">
          <div className="k-lab">
            <Activity size={15} />
            금일 발전량
          </div>
          <div className="k-val">582.4<span className="u">MWh</span></div>
          <div className="k-sub up">▲ 8.2% 목표대비</div>
        </div>
        <div className="kpi">
          <div className="k-lab">
            <Database size={15} />
            평균 발전시간
          </div>
          <div className="k-val">4.68<span className="u">h</span></div>
          <div className="k-sub up">▲ 0.15h 평년대비</div>
        </div>
        <div className="kpi">
          <div className="k-lab">
            <ShieldAlert size={15} style={{ color: 'var(--red)' }} />
            경보 발생
          </div>
          <div className="k-val" style={{ color: 'var(--red)' }}>1<span className="u" style={{ color: 'var(--red)' }}>건</span></div>
          <div className="k-sub down">인버터 #4 통신 지연</div>
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: 22 }}>
        {/* Chart Card */}
        <div className="card block" style={{ minHeight: 320, display: 'flex', flexDirection: 'column' }}>
          <h3>발전량 추이 (금월 누적)</h3>
          <div className="h-sub" style={{ marginBottom: 25 }}>일별 실적 발전량과 예측 발전량 비교</div>
          <div className="bars" style={{ flex: 1, display: 'flex', alignItems: 'flex-end', gap: 14, paddingTop: 10, paddingBottom: 15 }}>
            {/* 5일치 데이터 비교 바 */}
            <div className="bar-col" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%', justifyContent: 'flex-end' }}>
              <div className="bar-stack" style={{ width: '100%', maxWidth: 42, display: 'flex', gap: 4, alignItems: 'flex-end', height: '100%' }}>
                <div className="bar actual" style={{ height: '70%', width: '50%', borderRadius: 4, background: 'var(--brand)' }} title="실적: 70MWh"></div>
                <div className="bar predict" style={{ height: '65%', width: '50%', borderRadius: 4, background: 'var(--mint)' }} title="예측: 65MWh"></div>
              </div>
              <div className="bar-x" style={{ fontSize: 11, color: 'var(--ink-faint)', fontWeight: 600 }}>06.13</div>
            </div>
            <div className="bar-col" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%', justifyContent: 'flex-end' }}>
              <div className="bar-stack" style={{ width: '100%', maxWidth: 42, display: 'flex', gap: 4, alignItems: 'flex-end', height: '100%' }}>
                <div className="bar actual" style={{ height: '55%', width: '50%', borderRadius: 4, background: 'var(--brand)' }} title="실적: 55MWh"></div>
                <div className="bar predict" style={{ height: '60%', width: '50%', borderRadius: 4, background: 'var(--mint)' }} title="예측: 60MWh"></div>
              </div>
              <div className="bar-x" style={{ fontSize: 11, color: 'var(--ink-faint)', fontWeight: 600 }}>06.14</div>
            </div>
            <div className="bar-col" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%', justifyContent: 'flex-end' }}>
              <div className="bar-stack" style={{ width: '100%', maxWidth: 42, display: 'flex', gap: 4, alignItems: 'flex-end', height: '100%' }}>
                <div className="bar actual" style={{ height: '85%', width: '50%', borderRadius: 4, background: 'var(--brand)' }} title="실적: 85MWh"></div>
                <div className="bar predict" style={{ height: '80%', width: '50%', borderRadius: 4, background: 'var(--mint)' }} title="예측: 80MWh"></div>
              </div>
              <div className="bar-x" style={{ fontSize: 11, color: 'var(--ink-faint)', fontWeight: 600 }}>06.15</div>
            </div>
            <div className="bar-col" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%', justifyContent: 'flex-end' }}>
              <div className="bar-stack" style={{ width: '100%', maxWidth: 42, display: 'flex', gap: 4, alignItems: 'flex-end', height: '100%' }}>
                <div className="bar actual" style={{ height: '90%', width: '50%', borderRadius: 4, background: 'var(--brand)' }} title="실적: 90MWh"></div>
                <div className="bar predict" style={{ height: '88%', width: '50%', borderRadius: 4, background: 'var(--mint)' }} title="예측: 88MWh"></div>
              </div>
              <div className="bar-x" style={{ fontSize: 11, color: 'var(--ink-faint)', fontWeight: 600 }}>06.16</div>
            </div>
            <div className="bar-col" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%', justifyContent: 'flex-end' }}>
              <div className="bar-stack" style={{ width: '100%', maxWidth: 42, display: 'flex', gap: 4, alignItems: 'flex-end', height: '100%' }}>
                <div className="bar actual" style={{ height: '40%', width: '50%', borderRadius: 4, background: 'var(--brand)' }} title="실적: 40MWh"></div>
                <div className="bar predict" style={{ height: '45%', width: '50%', borderRadius: 4, background: 'var(--mint)' }} title="예측: 45MWh"></div>
              </div>
              <div className="bar-x" style={{ fontSize: 11, color: 'var(--ink-faint)', fontWeight: 600 }}>오늘</div>
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 16, fontSize: 12, color: 'var(--ink-soft)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--brand)' }}></span>실적 발전량</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--mint)' }}></span>예측 발전량</span>
          </div>
        </div>

        {/* CCTV / Status Card */}
        <div className="card block" style={{ minHeight: 320, display: 'flex', flexDirection: 'column' }}>
          <h3>발전소 실시간 현황 (CCTV)</h3>
          <div className="h-sub">새만금 제1발전소 메인 인버터 구역</div>
          <div className="cctv-preview" style={{ flex: 1, background: '#121212', borderRadius: 10, position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyItems: 'center', justifyContent: 'center' }}>
            {/* Grid overlay */}
            <div style={{ position: 'absolute', inset: 0, opacity: 0.15, background: 'linear-gradient(rgba(18,90,70,0) 95%, rgba(18,90,70,1) 5%), linear-gradient(90deg, rgba(18,90,70,0) 95%, rgba(18,90,70,1) 5%)', backgroundSize: '20px 20px' }}></div>
            {/* CCTV Text */}
            <div style={{ position: 'absolute', top: 12, left: 14, color: '#00ff66', fontFamily: 'monospace', fontSize: 11, letterSpacing: 0.5 }}>
              CAM 01 // MAIN_INVERTER_ZONE<br />
              2026-06-18 15:00:24<br />
              STATUS: ONLINE
            </div>
            {/* Visual representation of solar field */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, width: '80%', opacity: 0.8 }}>
              <div style={{ display: 'flex', gap: 8 }}>
                <div style={{ flex: 1, height: 42, background: '#1e382f', border: '1px solid #2f5a4a', borderRadius: 4 }}></div>
                <div style={{ flex: 1, height: 42, background: '#1e382f', border: '1px solid #2f5a4a', borderRadius: 4 }}></div>
                <div style={{ flex: 1, height: 42, background: '#1e382f', border: '1px solid #2f5a4a', borderRadius: 4 }}></div>
                <div style={{ flex: 1, height: 42, background: '#1e382f', border: '1px solid #2f5a4a', borderRadius: 4 }}></div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <div style={{ flex: 1, height: 42, background: '#1e382f', border: '1px solid #2f5a4a', borderRadius: 4 }}></div>
                <div style={{ flex: 1, height: 42, background: '#1e382f', border: '1px solid #2f5a4a', borderRadius: 4 }}></div>
                <div style={{ flex: 1, height: 42, background: '#1d5442', border: '1px solid #00ff66', borderRadius: 4, position: 'relative' }}>
                  <span style={{ position: 'absolute', top: 4, right: 4, width: 6, height: 6, borderRadius: '50%', background: '#00ff66', animation: 'pulse 1.5s infinite' }}></span>
                </div>
                <div style={{ flex: 1, height: 42, background: '#1e382f', border: '1px solid #2f5a4a', borderRadius: 4 }}></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Asset Table */}
      <div className="card block">
        <h3>자산 목록</h3>
        <div className="h-sub" style={{ marginBottom: 16 }}>등록된 재생에너지 발전 자산</div>
        <table className="tbl">
          <thead>
            <tr><th>발전소명</th><th>위치</th><th>구분</th><th>용량</th><th>상태</th><th>상업운전일</th></tr>
          </thead>
          <tbody>
            <tr>
              <td><b>새만금 태양광 1호</b></td>
              <td>전라북도 군산시</td>
              <td>태양광</td>
              <td>80.0 MW</td>
              <td><span className="sev low">정상</span></td>
              <td>2024-03-15</td>
            </tr>
            <tr>
              <td><b>고흥 해상풍력 1호</b></td>
              <td>전라남도 고흥군</td>
              <td>풍력</td>
              <td>40.0 MW</td>
              <td><span className="sev low">정상</span></td>
              <td>2025-11-01</td>
            </tr>
            <tr>
              <td><b>제주 한림 태양광 2호</b></td>
              <td>제주특별자치도 제주시</td>
              <td>태양광</td>
              <td>4.5 MW</td>
              <td><span className="sev mid">점검</span></td>
              <td>2021-08-20</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  )
}
