import type { Member } from '../api/types'

/** Display names may repeat; use membership IDs to distinguish payment and split choices. */
export function labelMembers(members: Member[]): Member[] {
  const counts = new Map<string, number>()
  members.forEach(member => counts.set(member.display_name, (counts.get(member.display_name) || 0) + 1))
  return members.map(member => ({ ...member,
    display_name: counts.get(member.display_name)! > 1 ? `${member.display_name}（#${member.id}）` : member.display_name,
  }))
}
