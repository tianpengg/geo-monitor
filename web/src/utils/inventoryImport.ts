export async function readInventoryFile(file: File | null) {
  if (!file) throw new Error('请先选择一个本地目录文件')
  if (file.size > 1024 * 1024) throw new Error('文件超过 1 MiB')
  const format = file.name.split('.').at(-1)?.toLowerCase()
  if (format !== 'xml' && format !== 'csv' && format !== 'json')
    throw new Error('请选择 XML、CSV 或 JSON 文件')
  try {
    const text = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer())
    return { text, format }
  } catch {
    throw new Error('无法读取 UTF-8 文件，请检查编码后重试')
  }
}
