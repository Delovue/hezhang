import { describe, expect, it } from 'vitest'
import { centsToInput, formatCents, parseYuan } from '../src/utils/money'
import { parseActivityId, safeRedirect } from '../src/utils/activity'

describe('integer money boundary', () => {
  it('keeps an unset budget distinct from a zero budget', () => {
    expect(parseYuan(' ', true)).toBeNull()
    expect(parseYuan('0', true)).toBe(0)
    expect(centsToInput(null)).toBe('')
    expect(centsToInput(0)).toBe('0.00')
  })
  it.each([['0.29', 29], ['1.01', 101], ['0002.5', 250], [' 1234.56 ', 123456],
    ['90071992547409.91', Number.MAX_SAFE_INTEGER]])('parses %s without floating multiplication', (input, expected) => {
    expect(parseYuan(input)).toBe(expected)
  })
  it.each(['', '1.001', '-1', '1e3', 'NaN', 'Infinity', '1,000', '1.', '.1', '0x10', '90071992547409.92'])('rejects invalid or unsafe amount %s', (input) => {
    expect(() => parseYuan(input)).toThrow()
  })
  it('formats safe integer limits without rounding away a cent', () => {
    expect(formatCents(Number.MAX_SAFE_INTEGER)).toBe('90,071,992,547,409.91')
    expect(formatCents(-101)).toBe('-1.01')
    expect(formatCents(null)).toBe('未设置')
    expect(() => formatCents(1.1)).toThrow()
  })
})

describe('navigation inputs', () => {
  it.each(['0', '-1', '1.5', '1e2', '9007199254740992', 'abc', ['1']])('rejects invalid activity id %s', (input) => {
    expect(parseActivityId(input)).toBeNull()
  })
  it('accepts safe integer ids and confines login redirects to activity routes', () => {
    expect(parseActivityId('9007199254740991')).toBe(Number.MAX_SAFE_INTEGER)
    expect(safeRedirect('/activities/12')).toBe('/activities/12')
    for (const input of ['//evil.test', 'https://evil.test', '/login', '/activities/1?next=//evil.test', null]) {
      expect(safeRedirect(input)).toBe('/activities')
    }
  })
})
