const BASE = import.meta.env.VITE_API_BASE || ''

export class ApiError extends Error {
  constructor(status, payload) {
    const message =
      (payload && typeof payload.detail === 'string' && payload.detail) ||
      (payload && payload.detail && payload.detail.message) ||
      '요청을 처리하지 못했어요.'
    super(message)
    this.status = status
    this.payload = payload
  }
}

async function request(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    credentials: 'include',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const contentType = res.headers.get('content-type') || ''
  const isJson = contentType.includes('application/json')
  const payload = isJson ? await res.json().catch(() => null) : null
  if (!res.ok) {
    throw new ApiError(res.status, payload)
  }
  return payload
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body ?? {}),
  put: (path, body) => request('PUT', path, body ?? {}),
  del: (path) => request('DELETE', path),
  async blob(path) {
    const res = await fetch(`${BASE}${path}`, { credentials: 'include' })
    if (!res.ok) throw new ApiError(res.status, null)
    return res.blob()
  },
}

export function qs(params) {
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params || {})) {
    if (v === undefined || v === null || v === '') continue
    usp.set(k, v)
  }
  const s = usp.toString()
  return s ? `?${s}` : ''
}
