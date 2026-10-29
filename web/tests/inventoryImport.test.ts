import assert from 'node:assert/strict'
import test from 'node:test'
import { readInventoryFile } from '../src/utils/inventoryImport.ts'

test('inventory files preserve UTF-8 content and normalize supported extensions', async () => {
  for (const format of ['xml', 'csv', 'json']) {
    const file = new File(['\ufeff路径,标题'], `directory.${format.toUpperCase()}`)
    assert.deepEqual(await readInventoryFile(file), { text: '路径,标题', format })
  }
})
test('missing and unsupported files fail before import', async () => {
  await assert.rejects(readInventoryFile(null), /选择/)
  await assert.rejects(readInventoryFile(new File(['[]'], 'directory.html')), /XML、CSV 或 JSON/)
})
test('inventory byte boundary accepts 1 MiB and rejects larger files', async () => {
  assert.equal((await readInventoryFile(new File(['x'.repeat(1024 * 1024)], 'directory.csv'))).text.length, 1024 * 1024)
  await assert.rejects(readInventoryFile(new File(['x'.repeat(1024 * 1024 + 1)], 'directory.csv')), /超过 1 MiB/)
})
test('invalid UTF-8 cannot be silently imported with replacement characters', async () => {
  await assert.rejects(readInventoryFile(new File([new Uint8Array([0xff, 0xfe])], 'directory.json')), /UTF-8/)
})
test('file read failures produce a safe recoverable message', async () => {
  class UnreadableFile extends File { async arrayBuffer(): Promise<ArrayBuffer> { throw new Error('private-local-path') } }
  await assert.rejects(readInventoryFile(new UnreadableFile(['[]'], 'directory.json')), error => {
    assert.match((error as Error).message, /无法读取 UTF-8/)
    assert.ok(!(error as Error).message.includes('private-local-path'))
    return true
  })
})
