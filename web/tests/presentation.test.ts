import assert from 'node:assert/strict'
import test from 'node:test'
import { bytes, dateError, healthPresentation, number, time, trendSegments, verificationInfo } from '../src/utils/presentation.ts'

test('unknown counts and timestamps never become observed zeros or current time', () => {
  assert.equal(number(undefined), '—')
  assert.equal(number(0), '0')
  assert.equal(time(null), '暂无')
  assert.equal(bytes(null), '未知')
  assert.equal(bytes(0), '0 B')
  assert.equal(bytes(128 * 1024), '128 KB')
})
test('event timestamps respect the website timezone', () => {
  assert.match(time(0, 'Asia/Shanghai', true), /08:00:00/)
  assert.match(time(0, 'UTC', true), /00:00:00/)
})
test('unobserved periods break the line while observed zero remains a real point', () => {
  const points = [
    { date: '1', requests: 5, coverage: 'observed' },
    { date: '2', requests: null, coverage: 'unobserved' },
    { date: '3', requests: 0, coverage: 'observed' },
    { date: '4', requests: 7, coverage: 'incomplete' },
  ]
  assert.deepEqual(trendSegments(points).map(s => s.map(p => p.date)), [['1'], ['3', '4']])
  assert.deepEqual(trendSegments([{ date: '1', requests: 99, coverage: 'unobserved' }]), [])
})
test('missing and unfamiliar health states do not imply normal collection', () => {
  assert.equal(healthPresentation(null).label, '状态未知')
  const future = healthPresentation({ overall: 'future', message: '', gaps: [], origin_note: '' })
  assert.equal(future.label, '状态未知')
  assert.equal(future.connection, '待确认')
})
test('disconnect and stale data never claim current reading or processing success', () => {
  const disconnected = { overall: 'disconnected', message: '采集器断连', gaps: [], origin_note: '' }
  assert.equal(healthPresentation(disconnected).connection, '已断连')
  assert.equal(healthPresentation(disconnected).reading, '待确认')
  assert.equal(healthPresentation({ ...disconnected, overall: 'healthy' }, true).label, '状态待刷新')
})
test('backlog, read errors and limited completeness have distinct status', () => {
  const base = { message: '', gaps: [], origin_note: '' }
  assert.equal(healthPresentation({ ...base, overall: 'backlog' }).processing, '补采中')
  assert.equal(healthPresentation({ ...base, overall: 'error', state: 'read_error' }).reading, '读取异常')
  assert.equal(healthPresentation({ ...base, overall: 'degraded' }).tone, 'warning')
})
test('verification distinguishes declarations, mismatches, unavailable and expired evidence', () => {
  assert.equal(verificationInfo('verified').label, '已核验')
  assert.equal(verificationInfo('ua_only').label, '仅 UA 匹配')
  assert.equal(verificationInfo('ip_mismatch').label, 'IP 不匹配')
  assert.equal(verificationInfo('evidence_unavailable').label, '证据暂不可用')
  assert.equal(verificationInfo('evidence_unavailable', 10, 20).label, '证据已过期')
  assert.equal(verificationInfo('surprise').label, '核验状态未知')
})
test('partial and reversed date ranges are rejected without changing applied filters', () => {
  assert.equal(dateError('2026-10-01', ''), '请同时填写开始和结束日期')
  assert.equal(dateError('2026-10-10', '2026-10-01'), '开始日期不能晚于结束日期')
  assert.equal(dateError('', ''), '')
  assert.equal(dateError('2026-10-01', '2026-10-01'), '')
})
