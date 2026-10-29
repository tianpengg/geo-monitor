import assert from 'node:assert/strict'
import test from 'node:test'
import { matchingOptions, monthDays, shiftDate, shiftMonth, todayDate, validDate } from '../src/utils/controls.ts'
import { dateError } from '../src/utils/presentation.ts'

test('custom option search matches names and tokens without changing options', () => {
  const options = [{value:'',label:'全部'},{value:'KimiBot',label:'Kimi 训练爬虫'},{value:'GPTBot',label:'OpenAI 训练爬虫'}]
  assert.equal(matchingOptions(options,' kimibot ')[0]?.value,'KimiBot')
  assert.equal(matchingOptions(options,'训练').length,2)
  assert.equal(matchingOptions(options,'not-found').length,0)
  assert.equal(matchingOptions(options,'').length,3)
  assert.equal(options[0]?.value,'')
})
test('typed dates reject impossible dates, partial dates and normalization', () => {
  assert.equal(validDate('2024-02-29'),true)
  for(const value of ['2026-02-29','2026-04-31','2026-2-1','0000-01-01','2026-13-01','bad']) assert.equal(validDate(value),false)
  assert.match(dateError('2026-02-30','2026-03-01'),/有效日期/)
  assert.match(dateError('2026-10-29','2026-10-28'),/不能晚于/)
})
test('calendar renders six Monday-start weeks with leap days and adjacent months', () => {
  const days=monthDays('2024-02-15')
  assert.equal(days.length,42)
  assert.equal(days[0]?.value,'2024-01-29')
  assert.equal(days.at(-1)?.value,'2024-03-10')
  assert.equal(days.filter(day=>day.current).length,29)
  assert.ok(days.every(day=>validDate(day.value)))
})
test('month and keyboard day shifts preserve dates across year and leap boundaries', () => {
  assert.equal(shiftMonth('2024-01-31',1),'2024-02-29')
  assert.equal(shiftMonth('2023-01-31',1),'2023-02-28')
  assert.equal(shiftMonth('2026-12-31',1),'2027-01-31')
  assert.equal(shiftMonth('2024-03-31',-1),'2024-02-29')
  assert.equal(shiftDate('2024-02-28',1),'2024-02-29')
  assert.equal(shiftDate('2026-12-31',1),'2027-01-01')
})
test('calendar today follows the configured website timezone', () => {
  const now=new Date('2026-10-28T23:30:00Z')
  assert.equal(todayDate('Asia/Shanghai',now),'2026-10-29')
  assert.equal(todayDate('America/Los_Angeles',now),'2026-10-28')
})
