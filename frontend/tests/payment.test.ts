import { describe, expect, it } from 'vitest'
import type { Payment, PaymentStatus } from '../src/api/types'
import { allowedPaymentActions } from '../src/utils/payment'
const payment: Payment = { id: 1, activity_id: 2, payer_member_id: 10, payee_member_id: 20, amount_cents: 2000, status: 'PENDING', created_at: '', updated_at: '' }
describe('payment action visibility', () => {
  it('only the payee can confirm or reject, while the payer can cancel', () => {
    expect(allowedPaymentActions(payment, 20)).toEqual(['confirm', 'reject'])
    expect(allowedPaymentActions(payment, 10)).toEqual(['cancel'])
    expect(allowedPaymentActions(payment, 30)).toEqual([])
    expect(allowedPaymentActions(payment, undefined)).toEqual([])
  })
  it.each<PaymentStatus>(['CONFIRMED', 'REJECTED', 'CANCELLED'])('makes %s immutable for both parties', status => {
    expect(allowedPaymentActions({ ...payment, status }, 10)).toEqual([])
    expect(allowedPaymentActions({ ...payment, status }, 20)).toEqual([])
  })
})
