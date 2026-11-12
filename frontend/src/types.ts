export interface User { id: string; username: string }
export interface Family { id: string; name: string }
export interface Member { id: string; username: string; joined_at: string }
export interface FamilyDetail extends Family { members: Member[] }
export interface Invite { id: string; code: string; expires_at: string }
export interface InvitePreview { family_id: string; family_name: string; already_member: boolean }
export interface PathNode { id: string; name: string }

export interface Location {
  id: string
  name: string
  note: string
  parent_id: string | null
  path: PathNode[]
  updated_at: string
  updated_by_name: string | null
}

export interface Item {
  id: string
  name: string
  barcode: string | null
  note: string
  location_id: string
  path: PathNode[]
  updated_at: string
  updated_by_name: string | null
}

export interface LocationDetail extends Location {
  children: Location[]
  items: Item[]
}
