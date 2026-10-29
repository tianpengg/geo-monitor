import assert from 'node:assert/strict'
import test from 'node:test'
import { timezoneOptions } from '../src/utils/timezones.ts'
import { matchingOptions } from '../src/utils/controls.ts'

test('common timezones use region identifiers accepted for date formatting', () => {
  const choices = timezoneOptions('', [])
  assert.equal(choices[0]?.value, 'Asia/Shanghai')
  assert.ok(choices.some(choice => choice.value === 'America/New_York'))
  assert.ok(choices.some(choice => choice.value === 'UTC'))
  for (const choice of choices) assert.doesNotThrow(() => new Intl.DateTimeFormat('zh-CN', { timeZone: choice.value }))
})
test('timezone search accepts Chinese cities and case-insensitive IANA identifiers', () => {
  const choices = timezoneOptions('', [])
  assert.equal(matchingOptions(choices, '北京')[0]?.value, 'Asia/Shanghai')
  assert.equal(matchingOptions(choices, '纽约')[0]?.value, 'America/New_York')
  assert.equal(matchingOptions(choices, 'america/new_york')[0]?.value, 'America/New_York')
})
test('browser catalog merges without duplicate values or losing Chinese labels', () => {
  const choices = timezoneOptions('Asia/Shanghai', ['Asia/Shanghai', 'UTC', 'Pacific/Honolulu', 'Pacific/Honolulu'])
  assert.equal(new Set(choices.map(choice => choice.value)).size, choices.length)
  assert.match(choices.find(choice => choice.value === 'Asia/Shanghai')!.label, /北京/)
  assert.equal(choices.find(choice => choice.value === 'Pacific/Honolulu')?.label, 'Pacific/Honolulu')
})
test('saved timezone absent from catalog is kept selectable without resetting', () => {
  const choices = timezoneOptions('Pacific/Chatham', [])
  assert.equal(choices[0]?.value, 'Pacific/Chatham')
  assert.match(choices[0]!.label, /当前配置/)
  assert.ok(choices.some(choice => choice.value === 'Asia/Shanghai'))
})
test('catalog lookup failure falls back to common and saved zones', t => {
  t.mock.method(Intl, 'supportedValuesOf', () => { throw new RangeError('unavailable') })
  const choices = timezoneOptions('Pacific/Chatham')
  assert.ok(choices.some(choice => choice.value === 'Asia/Shanghai'))
  assert.ok(choices.some(choice => choice.value === 'Pacific/Chatham'))
})
