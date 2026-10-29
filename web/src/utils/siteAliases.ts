export function parseSiteAliases(value: string): string[] {
  const aliases = value.split(/[\n,，]+/).map(item => item.trim()).filter(Boolean)
  if (aliases.length > 10) throw new Error('官网别名最多 10 个，请删除多余域名后保存')
  return aliases
}
