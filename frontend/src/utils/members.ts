import type { Member } from '../api/types'

/** Display names may repeat; use membership IDs to distinguish payment and split choices. */
export function labelMembers(members: Member[]): Member[] {
  const counts = new Map<string, number>()
  members.forEach(member => counts.set(member.display_name, (counts.get(member.display_name) || 0) + 1))
  return members.map(member => ({ ...member,
    display_name: counts.get(member.display_name)! > 1 ? `${member.display_name}（#${member.id}）` : member.display_name,
  }))
}

/** 头像文字：中文名取最后一个字（“小王”取“王”），其他取首字母大写；重名附加的编号不参与。 */
export function initial(name: string): string {
  const chars = Array.from(name.replace(/（#\d+）$/, '').trim())
  const last = chars.at(-1)
  if (!last) return '?'
  return /\p{Script=Han}/u.test(last) ? last : chars[0]!.toUpperCase()
}

/** 按编号固定头像配色，同一成员在各页面颜色一致。 */
export function avatarTone(id: number): string {
  return `tone-${Math.abs(id) % 5}`
}
