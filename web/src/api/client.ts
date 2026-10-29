let csrfToken = ''

export class ApiError extends Error {
  readonly status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export function setCsrf(token: string): void {
  csrfToken = token
}

export async function apiCsv(path: string): Promise<Blob> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      credentials: 'same-origin',
      headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {},
    })
  } catch {
    throw new Error('无法连接服务，请检查网络后重试')
  }
  if (!response.ok) {
    let detail: unknown
    try {
      detail = (await response.json()).detail
    } catch {
      /* Preserve authentication status even for invalid error JSON. */
    }
    throw new ApiError(typeof detail === 'string' ? detail : '导出失败，请重试', response.status)
  }
  if (!response.headers.get('Content-Type')?.includes('text/csv'))
    throw new Error('导出响应格式异常，请重试')
  return response.blob()
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  if (csrfToken) headers.set('X-CSRF-Token', csrfToken)
  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...options, headers, credentials: 'same-origin' })
  } catch {
    throw new Error('无法连接服务，请检查网络后重试')
  }
  let result: { detail?: unknown }
  try {
    result = await response.json()
  } catch {
    throw new ApiError('服务响应异常，请稍后重试', response.status)
  }
  if (!response.ok)
    throw new ApiError(
      typeof result.detail === 'string' ? result.detail : '请求失败',
      response.status,
    )
  return result as T
}
