import { EditableText } from './editors'
import Lines from './Lines'
import type { PermitStage } from '../types'

const NL = String.fromCharCode(10)

/** "허가번호: 제2025-68호" 줄들을 {라벨: 값} 으로. 정의에 없는 줄은 rest 에 남긴다. */
export function parseContent(content: string, fields: string[]) {
  const values: Record<string, string> = {}
  const rest: string[] = []
  for (const line of (content || '').split(NL)) {
    if (!line.trim()) continue
    const at = line.indexOf(':')
    const label = at > 0 ? line.slice(0, at).trim() : ''
    if (label && fields.includes(label)) values[label] = line.slice(at + 1).trim()
    else rest.push(line)
  }
  return { values, rest }
}

/** 칸 값을 다시 한 덩어리 텍스트로. 값이 빈 칸은 줄을 만들지 않는다. */
export function buildContent(values: Record<string, string>, fields: string[], rest: string[]) {
  return [
    ...fields.filter(f => (values[f] || '').trim()).map(f => `${f}: ${values[f].trim()}`),
    ...rest,
  ].join(NL)
}

// 인허가 항목의 본문. 채울 칸이 정해진 항목(허가번호·용량·면적 등)은
// 칸마다 값만 넣게 하고, 정해지지 않은 항목은 지금처럼 자유 입력이다.
export default function StageContent({ stage, editable, canEdit, onSave }: {
  stage: PermitStage
  editable: boolean
  canEdit: boolean
  onSave: (content: string) => Promise<void>
}) {
  const fields = stage.content_fields || []

  if (fields.length === 0) {
    return editable
      ? <EditableText value={stage.content} multiline disabled={!canEdit}
                      placeholder="내용" onSave={onSave} />
      : <div className="bz-stage-content"><Lines text={stage.content} /></div>
  }

  const { values, rest } = parseContent(stage.content, fields)

  if (!editable) {
    const filled = fields.filter(f => (values[f] || '').trim())
    if (filled.length === 0 && rest.length === 0) {
      return <div className="bz-stage-content bz-muted">내용 미입력</div>
    }
    return (
      <dl className="bz-stage-fields">
        {filled.map(f => (
          <div key={f} className="bz-sfield">
            <dt>{f}</dt>
            <dd title={values[f]}>{values[f]}</dd>
          </div>
        ))}
        {rest.length > 0 && (
          <div className="bz-sfield">
            <dt />
            <dd><Lines text={rest.join(NL)} /></dd>
          </div>
        )}
      </dl>
    )
  }

  return (
    <dl className="bz-stage-fields">
      {fields.map(f => (
        <div key={f} className="bz-sfield">
          <dt>{f}</dt>
          <dd>
            <EditableText value={values[f] || ''} disabled={!canEdit} placeholder="미정"
                          onSave={v => onSave(buildContent({ ...values, [f]: v }, fields, rest))} />
          </dd>
        </div>
      ))}
    </dl>
  )
}
