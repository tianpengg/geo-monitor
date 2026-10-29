import type { CrawlerRule, CrawlerRuleInput } from '../types'

export type RuleDraft = Omit<CrawlerRuleInput, 'enabled' | 'evidence_url' | 'documentation_url' | 'revision'> & {
  enabled: string; evidence_url: string; documentation_url: string
}
export function ruleDraft(rule?: CrawlerRule): RuleDraft {
  return {
    token: rule?.token ?? '', match_token: rule?.match_token ?? '', name: rule?.name ?? '',
    operator: rule?.operator ?? '', product_attribution: rule?.product_attribution ?? '产品归属未确认',
    evidence_url: rule?.evidence_url ?? '', documentation_url: rule?.documentation_url ?? '',
    evidence_format: rule?.evidence_format ?? 'json', enabled: rule?.enabled === false ? 'false' : 'true',
  }
}
export function rulePayload(draft: RuleDraft, revision?: number): CrawlerRuleInput {
  if (!/^[A-Za-z][A-Za-z0-9_-]{1,99}$/.test(draft.token.trim()) ||
      !/^[A-Za-z][A-Za-z0-9_-]{1,99}$/.test(draft.match_token.trim()))
    throw new Error('标识与 UA 匹配词须为 2–100 个英文字符、数字、下划线或短横线，以字母开头')
  if (![draft.name, draft.operator, draft.product_attribution].every(value => value.trim()))
    throw new Error('请填写名称、运营方和产品归属说明')
  return {
    ...draft, token: draft.token.trim(), match_token: draft.match_token.trim(),
    name: draft.name.trim(), operator: draft.operator.trim(), product_attribution: draft.product_attribution.trim(),
    evidence_url: draft.evidence_url.trim() || null, documentation_url: draft.documentation_url.trim() || null,
    enabled: draft.enabled === 'true', ...(revision ? { revision } : {}),
  }
}
export function editableRule(rule: CrawlerRule): CrawlerRuleInput {
  return rulePayload(ruleDraft(rule), rule.revision)
}
export function searchRules(rules: CrawlerRule[], query: string): CrawlerRule[] {
  const text = query.trim().toLowerCase()
  return rules.filter(rule => [rule.token, rule.match_token, rule.name, rule.operator, rule.product_attribution]
    .some(value => value.toLowerCase().includes(text)))
}
