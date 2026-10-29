import assert from 'node:assert/strict'
import test from 'node:test'
import { editableRule, ruleDraft, rulePayload, searchRules } from '../src/utils/crawlerRules.ts'
import type { CrawlerRule } from '../src/types/index.ts'

const rule: CrawlerRule = {
  token: 'StableBot', match_token: 'NewAgentBot', name: '搜索爬虫', operator: 'Example AI',
  product_attribution: '产品归属未确认', evidence_url: null, documentation_url: null,
  evidence_format: 'json', enabled: false, revision: 7, origin: 'custom', version: 'StableBot@7',
  updated_at: 1, evidence_state: 'not_configured', evidence_fetched_at: null,
}
test('new drafts reset identifiers and send optional empty sources as null', () => {
  const draft = ruleDraft()
  assert.equal(draft.token, '')
  assert.equal(draft.enabled, 'true')
  assert.throws(() => rulePayload(draft), /标识/)
  Object.assign(draft, { token: ' NewBot ', match_token: ' NewBot ', name: 'New crawler', operator: 'New platform' })
  const input = rulePayload(draft)
  assert.equal(input.token, 'NewBot')
  assert.equal(input.evidence_url, null)
  assert.equal(input.enabled, true)
  assert.ok(!('revision' in input))
})
test('editing keeps stable identity and revision, excluding server metadata', () => {
  const body = editableRule(rule)
  assert.equal(body.token, 'StableBot')
  assert.equal(body.match_token, 'NewAgentBot')
  assert.equal(body.revision, 7)
  assert.equal(body.enabled, false)
  assert.ok(!('version' in body))
  assert.ok(!('origin' in body))
  assert.ok(!('evidence_state' in body))
})
test('search includes disabled identities, updated match words and operators', () => {
  for (const text of [' stablebot ', 'newagent', 'EXAMPLE AI', '搜索'])
    assert.deepEqual(searchRules([rule], text), [rule])
  assert.deepEqual(searchRules([rule], 'missing'), [])
})
test('partial tokens and incomplete identity metadata cannot become a saved rule', () => {
  assert.throws(() => rulePayload({ ...ruleDraft(rule), match_token: '.*Bot' }), /标识/)
  assert.throws(() => rulePayload({ ...ruleDraft(rule), operator: ' ' }), /运营方/)
})
