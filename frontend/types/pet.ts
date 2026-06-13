export interface PetNotification {
  id: string
  course_id?: string | null
  notification_type: string
  title: string
  reason?: string | null
  source_type: string
  source_id?: string | null
  action_url: string
  is_read: boolean
  created_at: string
}

export interface PetFeed {
  items: PetNotification[]
  unread_count: number
}

export interface PetPreference {
  study_reminders_enabled: boolean
  interval_hours: 1 | 2 | 4
  quiet_start: string
  quiet_end: string
}
