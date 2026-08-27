// /api/bizdev fetch 헬퍼 — 기존 관례(fetch + credentials + CSRF 헤더)를 따른다.

const getCsrf = async (): Promise<string> => {
  const res = await fetch('/api/auth/csrf/', { credentials: 'include' })
  return (await res.json()).csrfToken
}

const parseError = async (res: Response): Promise<string> => {
  try {
    const data = await res.json()
    if (typeof data === 'string') return data
    return data.error || data.detail || JSON.stringify(data)
  } catch {
    return `요청 실패 (${res.status})`
  }
}

export async function apiGet<T>(url: string): Promise<T> {
  const res = await fetch(url, { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function apiSend<T>(method: string, url: string, body?: unknown): Promise<T> {
  const csrf = await getCsrf()
  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  if (res.status === 204) return undefined as T
  return res.json()
}

export async function apiUpload<T>(url: string, form: FormData): Promise<T> {
  const csrf = await getCsrf()
  // FormData 는 Content-Type 을 브라우저가 정한다 (boundary 포함)
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': csrf },
    body: form,
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
