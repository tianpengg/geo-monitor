import assert from 'node:assert/strict'
import test from 'node:test'
import { ApiError, api, apiCsv, setCsrf } from '../src/api/client.ts'
import { collectorInstallCommand } from '../src/utils/installation.ts'

for (const scheme of ['http', 'https']) {
  test(`${scheme} collector command preserves transport and keeps credentials out of arguments`, () => {
    const protocols = scheme === 'https' ? '=https' : '=http,https'
    const command = collectorInstallCommand({
      server_url: `${scheme}://monitor.example.test:8000`,
      site_id: 'synthetic-site', source_id: 'synthetic-source', token: 'synthetic-private-token',
    })
    assert.ok(command.includes(`--proto '${protocols}' --proto-redir '${protocols}'`))
    assert.ok(command.includes(`${scheme}://monitor.example.test:8000/downloads/install-collector.sh`))
    assert.ok(command.includes("'synthetic-site' 'synthetic-source'"))
    assert.ok(!command.includes('synthetic-private-token'))
    assert.ok(!command.includes('--insecure'))
  })
}

test('API requests keep same-origin cookies and CSRF with JSON writes', async () => {
  const original = globalThis.fetch
  setCsrf('controlled-test-csrf')
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/api/site')
      assert.equal(options?.credentials, 'same-origin')
      assert.equal(new Headers(options?.headers).get('X-CSRF-Token'), 'controlled-test-csrf')
      assert.equal(new Headers(options?.headers).get('Content-Type'), 'application/json')
      return Response.json({ domain: 'example.test' })
    }
    assert.deepEqual(await api('/site', { method: 'PUT', body: '{}' }), { domain: 'example.test' })
  } finally { globalThis.fetch = original; setCsrf('') }
})

test('authentication status survives malformed error responses', async () => {
  const original = globalThis.fetch
  try {
    globalThis.fetch = async () => new Response('not-json', { status: 401 })
    await assert.rejects(api('/auth/me'), error => error instanceof ApiError && error.status === 401)
    globalThis.fetch = async () => Response.json({ detail: '请先登录' }, { status: 401 })
    await assert.rejects(api('/auth/me'), error => error instanceof ApiError && error.message === '请先登录')
  } finally { globalThis.fetch = original }
})

test('network failures are readable and structured error bodies are not echoed', async () => {
  const original = globalThis.fetch
  try {
    globalThis.fetch = async () => { throw new TypeError('internal connection data') }
    await assert.rejects(api('/overview'), /无法连接服务/)
    globalThis.fetch = async () => Response.json({ detail: { private: 'not a user-facing error' } }, { status: 422 })
    await assert.rejects(api('/site'), error => error instanceof ApiError && error.message === '请求失败')
  } finally { globalThis.fetch = original }
})

test('CSV downloads retain authentication, return real bytes and reject failures', async () => {
  const original = globalThis.fetch
  setCsrf('csv-test-csrf')
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/api/events/export?q=%25&status=4xx')
      assert.equal(options?.credentials, 'same-origin')
      assert.equal(new Headers(options?.headers).get('X-CSRF-Token'), 'csv-test-csrf')
      return new Response('path,status\r\n/a,403\r\n', { headers: { 'Content-Type': 'text/csv; charset=utf-8' } })
    }
    assert.equal(await (await apiCsv('/events/export?q=%25&status=4xx')).text(), 'path,status\r\n/a,403\r\n')
    globalThis.fetch = async () => Response.json({ detail: '导出超过 10000 条' }, { status: 400 })
    await assert.rejects(apiCsv('/events/export'), /10000/)
    globalThis.fetch = async () => new Response('invalid', { status: 401 })
    await assert.rejects(apiCsv('/events/export'), error => error instanceof ApiError && error.status === 401)
    globalThis.fetch = async () => Response.json({ items: [] })
    await assert.rejects(apiCsv('/events/export'), /格式异常/)
    globalThis.fetch = async () => { throw new TypeError('private debug') }
    await assert.rejects(apiCsv('/events/export'), /无法连接服务/)
  } finally { globalThis.fetch = original; setCsrf('') }
})
