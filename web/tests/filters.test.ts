import assert from 'node:assert/strict'
import test from 'node:test'
import { useFilters } from '../src/composables/useFilters.ts'

test('shared filters preserve overview and detail query contracts after extraction', () => {
  const filters = useFilters()
  Object.assign(filters.applied.value, { start: '2026-10-01', end: '2026-10-28', crawler: 'KimiBot', q: '/docs', status: '4xx', verification: 'verified', path: '/docs/guide' })
  assert.deepEqual(Object.fromEntries(filters.params()), { days: '7', start: '2026-10-01', end: '2026-10-28' })
  assert.deepEqual(Object.fromEntries(filters.params(true, 'cursor-1')), { days: '7', start: '2026-10-01', end: '2026-10-28', crawler: 'KimiBot', q: '/docs', status: '4xx', verification: 'verified', path: '/docs/guide', cursor: 'cursor-1' })
})

test('filter reset clears applied and draft values without leaking across workspaces', () => {
  const first = useFilters(), second = useFilters()
  first.draftCrawler.value = 'GPTBot'
  first.applied.value.crawler = 'GPTBot'
  assert.equal(second.draftCrawler.value, '')
  assert.equal(second.applied.value.crawler, '')
  first.resetFilters()
  assert.equal(first.draftCrawler.value, '')
  assert.deepEqual(Object.fromEntries(first.params(true)), { days: '7' })
})
