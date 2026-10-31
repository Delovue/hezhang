import type { Payment, PaymentAction, PaymentStatus } from '../api/types'
export const paymentLabels: Record<PaymentStatus, string> = { PENDING: '待收款人确认', CONFIRMED: '已确认', REJECTED: '已拒绝', CANCELLED: '已撤销' }
export const paymentActions: Record<PaymentAction, string> = { confirm: '确认收款', reject: '拒绝付款', cancel: '撤销登记' }
export function allowedPaymentActions(payment: Payment, memberId: number | undefined): PaymentAction[] {
  if (payment.status !== 'PENDING') return []
  if (payment.payee_member_id === memberId) return ['confirm', 'reject']
  if (payment.payer_member_id === memberId) return ['cancel']
  return []
}
