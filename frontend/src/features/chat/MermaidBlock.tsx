import { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'

/**
 * mermaid 코드블록을 도식으로 렌더링한다.
 *
 * 설계 원칙
 * - **깨지면 원본을 보여준다.** LLM이 만든 문법이 항상 유효하진 않다.
 *   렌더 실패 시 빈 화면 대신 코드를 그대로 노출해, 최소한 내용은 읽을 수 있게 한다.
 * - 렌더는 이 컴포넌트 안에서만 일어난다. 스트리밍 중 미완성 코드가 들어와도
 *   부모 마크다운 렌더링에 영향을 주지 않는다.
 */

let initialized = false
function ensureInit() {
  if (initialized) return
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',   // 다이어그램 안의 클릭 핸들러·HTML 삽입 차단
    theme: 'base',
    // ⚠ 'inherit'을 쓰면 안 된다. mermaid는 SVG를 그리기 전에 글자 폭을 **측정해서**
    //   노드 박스 크기를 정하는데, 'inherit'은 실제 폰트가 아니라 측정이 빗나간다.
    //   영문 기준 폭으로 계산한 박스에 더 넓은 한글이 들어가 잘렸다
    //   (실측: '당진행복솔라 주식회사' → '당진행복솔라 주식호'). 실제 폰트를 명시한다.
    fontFamily: '"Pretendard","Pretendard Variable","Apple SD Gothic Neo","Malgun Gothic",sans-serif',
    fontSize: 14,
    flowchart: {
      // HTML 라벨은 브라우저가 직접 줄바꿈·폭을 처리해 CJK 잘림에 강하다.
      htmlLabels: true,
      wrappingWidth: 200,   // 긴 한글 라벨을 강제로 접어 가로 폭 폭주를 막는다
      curve: 'basis',
      padding: 14,
      nodeSpacing: 42,
      rankSpacing: 52,
      useMaxWidth: true,
    },
    themeVariables: {
      primaryColor: '#E5F4EE',        // --mint-soft
      primaryTextColor: '#14201B',    // --ink
      primaryBorderColor: '#2F8268',  // --green-accent
      lineColor: '#8A988F',           // --ink-faint
      secondaryColor: '#FBFCFB',      // --surface-2
      tertiaryColor: '#FFFFFF',
      // subgraph(클러스터) — 기본 회색이라 앱과 겉돌던 부분
      clusterBkg: '#FBFCFB',
      clusterBorder: '#E4EAE5',
      edgeLabelBackground: '#F4F7F4', // --bg. 라벨 뒤 흰 박스가 선을 끊어 보이게 하던 것
      titleColor: '#153F35',
    },
  })
  initialized = true
}

/** 본문 폰트(Pretendard)가 실제로 준비될 때까지 기다린다.
 *
 *  Pretendard는 jsDelivr 웹폰트다(index.html). mermaid는 SVG를 그리기 전에 글자 폭을
 *  **측정해서** 노드 박스 크기를 정하는데, 그 시점에 웹폰트가 아직 안 왔으면
 *  폴백(맑은 고딕)으로 재고, 직후 Pretendard가 도착하면 글자가 넓어져 박스를 넘친다.
 *  (실측: '당진행복솔라 주식회사'가 '당진행복솔라 주식호'로 잘림)
 *  답변이 스트리밍되며 도식이 늦게 그려질수록 이 경합이 잘 난다.
 */
async function fontsReady() {
  const fonts = (document as Document & { fonts?: FontFaceSet }).fonts
  if (!fonts) return
  try {
    await fonts.load('14px Pretendard')
    await fonts.ready
  } catch {
    /* 폰트를 못 받아도 렌더는 진행한다 — 폴백 폭으로 일관되게 측정되므로 잘리지 않는다 */
  }
}

let seq = 0

/** 스트리밍이 멈춘 것으로 볼 시간. 델타 간격보다 넉넉해야 오탐이 없다. */
const STALL_MS = 2500

/** mermaid가 body에 남긴 임시·오류 노드를 지운다.
 *
 *  render()가 실패하면 mermaid는 "Syntax error in text" SVG를 만들어 두고 throw한다.
 *  그 노드가 body에 남아 화면 하단에 쌓인다. 우리 id뿐 아니라 mermaid가 자체 생성하는
 *  오류 컨테이너(dmermaid-*)도 함께 정리해야 한다.
 */
function sweepStrays(id?: string) {
  if (id) document.getElementById(`d${id}`)?.remove()
  document
    .querySelectorAll('body > [id^="dmmd-"], body > [id^="dmermaid-"], body > .mermaid-tmp')
    .forEach(el => el.remove())
}

export default function MermaidBlock({ code }: { code: string }) {
  const [svg, setSvg] = useState('')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [stalled, setStalled] = useState(false)
  const hostRef = useRef<HTMLDivElement>(null)

  // code가 바뀌면 대기 시계를 되감는다 — 스트리밍이 멈춘 뒤에만 폴백이 뜬다
  useEffect(() => {
    setStalled(false)
    const t = setTimeout(() => setStalled(true), STALL_MS)
    return () => clearTimeout(t)
  }, [code])

  useEffect(() => {
    let cancelled = false
    const source = code.trim()
    if (!source) return

    ensureInit()
    const id = `mmd-${Date.now()}-${seq++}`

    fontsReady()
      .then(async () => {
        if (cancelled) throw new Error('cancelled')
        // **먼저 문법을 확인한다.** 답변이 스트리밍되는 동안 이 컴포넌트는 미완성
        // 코드로 수십 번 호출되는데, 곧바로 render()를 부르면 그때마다 mermaid가
        // 오류 SVG를 body에 만들어 두고 throw한다. 그 노드들이 화면 하단에
        // "Syntax error in text"로 쌓였다.
        // parse()는 suppressErrors로 던지지 않고 false만 돌려주므로 부작용이 없다.
        const ok = await mermaid.parse(source, { suppressErrors: true })
        if (cancelled) throw new Error('cancelled')
        if (!ok) {
          // 아직 오는 중이거나 정말 잘못된 코드. 어느 쪽이든 그리지 않는다.
          setPending(true)
          setSvg('')
          setError('')
          return null
        }
        setPending(false)
        return mermaid.render(id, source)
      })
      .then(res => {
        if (cancelled || !res) return
        setSvg(res.svg)
        setError('')
      })
      .catch((e: unknown) => {
        sweepStrays(id)
        if (cancelled) return
        setSvg('')
        setError(e instanceof Error ? e.message : String(e))
      })

    return () => {
      cancelled = true
      sweepStrays(id)
    }
  }, [code])

  if (error) {
    return (
      <div className="mermaid-fallback">
        <div className="mmd-err">도식을 그리지 못했습니다 · 원본 코드를 표시합니다</div>
        <pre><code>{code}</code></pre>
      </div>
    )
  }

  // 문법이 끝내 안 맞으면(스트리밍이 끝났는데도 parse 실패) 영원히 대기하지 않고
  // 원본을 보여준다. STALL_MS는 델타 간격보다 넉넉해야 스트리밍 중 오탐이 없다.
  if (pending && stalled) {
    return (
      <div className="mermaid-fallback">
        <div className="mmd-err">도식 문법을 해석하지 못했습니다 · 원본 코드를 표시합니다</div>
        <pre><code>{code}</code></pre>
      </div>
    )
  }

  if (!svg) {
    return <div className="mermaid-loading">도식 그리는 중…</div>
  }

  return (
    <div
      ref={hostRef}
      className="mermaid-block"
      // mermaid가 생성한 SVG. securityLevel:'strict'로 스크립트가 제거된 상태다.
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
