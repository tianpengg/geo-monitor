import assert from 'node:assert/strict'
import test from 'node:test'
import { parseSiteAliases } from '../src/utils/siteAliases.ts'

test('alias input accepts newlines, both commas, blank rows and CRLF', () => {
  assert.deepEqual(parseSiteAliases(' WWW.example.com \r\n\nalt.example.com, cdn.example.com， other.example.com '),
    ['WWW.example.com', 'alt.example.com', 'cdn.example.com', 'other.example.com'])
  assert.deepEqual(parseSiteAliases(' \n,， '), [])
})

test('alias input keeps exact host text for server validation and rejects over ten', () => {
  assert.deepEqual(parseSiteAliases('https://example.com/a,*.example.com'), ['https://example.com/a', '*.example.com'])
  assert.equal(parseSiteAliases(Array.from({ length: 10 }, (_, n) => `${n}.example.com`).join('\n')).length, 10)
  assert.throws(() => parseSiteAliases(Array.from({ length: 11 }, (_, n) => `${n}.example.com`).join(',')), /最多 10 个/)
})
