// 여러 줄 텍스트를 보기 전용으로 그린다(빈 값은 —).
export default function Lines({ text }: { text: string }) {
  const value = (text || '').trim()
  if (!value) return <span className="bz-muted">—</span>
  return (
    <span>
      {value.split('\n').map((line, i) => (
        <span key={i} className="bz-line">{line}</span>
      ))}
    </span>
  )
}
