import type { DataOverview } from './dataApi'
import type { LabAuthorization, Qualification, Person } from '@/types'
export interface PersonalSummary extends Omit<DataOverview, 'authorizations' | 'qualifications'> {
  profile: Person; updatedAt?: string; pendingApplications: number; unreadNotifications: number
  permitHistory: { id: string; lab_id: string; start_date: string; end_date: string; status: string; source_ref: string; created_at: string }[]
  authorizations: (LabAuthorization & { effectiveStatus: string; issues: string[]; hardwareStatus: string })[]
  qualifications: (Qualification & { effectiveStatus: string })[]
}
export interface AvailableLab { labId: string; labName: string; status: string; needsDouble: boolean; requiredCerts: string[]; issues: string[] }
export interface Application {
  id: string; user_id: string; person_id: string; lab_id: string; kind: string; purpose: string
  start_date: string; end_date: string; status: string; execution_status: string; version: number
  created_at: string; updated_at: string; execution_ref: string; applicant_name: string
  events: { id: number; action: string; note: string; actor_name: string; created_at: string }[]
  attachments: { id: string; name: string; media_type: string; created_at: string }[]
}
export interface Page<T> { items: T[]; total: number }
export interface Notification { id: number; title: string; body: string; is_read: number; created_at: string; application_id: string | null }
