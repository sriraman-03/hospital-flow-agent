export type Role = "administrator" | "operations_staff" | "department_staff" | "viewer";
export interface User { id: number; email: string; full_name: string; role: Role; department_id: number | null; is_active: boolean; created_at: string; last_login_at: string | null; }
export interface Me extends User { permissions: string[]; }
export interface Page<T> { items: T[]; total: number; page: number; page_size: number; pages: number; }

export interface Patient {
  id: number; patient_code: string; first_name: string; last_name: string; date_of_birth: string; phone: string | null; status: string;
  department_id: number | null; department_name: string | null; requested_department_id: number | null;
  bed_id: number | null; bed_code: string | null; admitted_at: string | null; discharged_at: string | null; created_at: string;
}
export interface HistoryEvent { timestamp: string; type: string; description: string; }
export interface Department {
  id: number; name: string; code: string; description: string | null; capacity: number; status: string; patient_count: number;
  total_beds: number; available_beds: number; occupied_beds: number; occupancy_pct: number; low_stock_resources: number;
}
export interface Bed { id: number; code: string; department_id: number; department_name: string; ward: string; status: string; patient_id: number | null; patient_code: string | null; }
export interface Assignment { id: number; bed_id: number; bed_code: string; patient_id: number; patient_code: string; assigned_at: string; released_at: string | null; release_reason: string | null; }
export interface Resource {
  id: number; name: string; category: string; unit: string; quantity: number; min_threshold: number; critical_threshold: number;
  department_id: number | null; department_name: string | null; storage_location: string; is_active: boolean; level: "ok" | "low" | "critical"; updated_at: string;
}
export interface Movement { id: number; resource_id: number; movement_type: string; quantity_change: number; quantity_before: number; quantity_after: number; reason: string | null; performed_by: number | null; created_at: string; }
export interface Transfer {
  id: number; patient_id: number; patient_code: string; source_department_id: number | null; source_department_name: string | null;
  destination_department_id: number; destination_department_name: string; destination_bed_id: number | null; destination_bed_code: string | null;
  status: string; reason: string | null; cancellation_reason: string | null; requested_at: string; approved_at: string | null; started_at: string | null; completed_at: string | null; cancelled_at: string | null;
}
export interface Discharge {
  id: number; patient_id: number; patient_code: string; department_name: string | null; status: string; notes: string | null;
  cancellation_reason: string | null; requested_at: string; approved_at: string | null; completed_at: string | null; cancelled_at: string | null;
}
export interface Notification {
  id: number; title: string; description: string; category: string; severity: "critical" | "warning" | "info" | "success"; created_at: string;
  is_read: boolean; read_at: string | null; is_acknowledged: boolean; acknowledged_at: string | null; is_resolved: boolean; resolved_at: string | null;
  resolution_note: string | null; entity_type: string | null; entity_id: number | null; dedup_key: string | null;
}
export interface UnreadCounts { unread: number; critical_active: number; by_category: Record<string, number>; }
export interface AuditLog { id: number; actor_id: number | null; actor_email: string | null; action: string; entity_type: string; entity_id: string | null; details: Record<string, unknown> | null; created_at: string; }
export interface DashboardSummary {
  total_patients: number; admitted_patients: number; available_beds: number; occupied_beds: number; total_beds: number; occupancy_rate: number;
  pending_admissions: number; pending_transfers: number; discharges_in_progress: number; low_stock_resources: number; unread_notifications: number; critical_active_alerts: number;
}
export interface Analytics {
  occupancy_by_department: { department: string; occupied: number; available: number; cleaning: number; out_of_service: number; occupancy_pct: number }[];
  admissions_vs_discharges: { date: string; admissions: number; discharges: number }[];
  resource_levels: { id: number; name: string; quantity: number; min_threshold: number; critical_threshold: number; unit: string }[];
  alerts_by_severity: { severity: string; count: number }[];
  critical_alerts: { id: number; title: string; description: string; severity: string; created_at: string; entity_type: string | null; entity_id: number | null; is_acknowledged: boolean }[];
  recent_activity: { id: number; action: string; entity_type: string; entity_id: string | null; actor: string | null; created_at: string }[];
}
export interface RoutingCandidate { department_id: number; department_name: string; eligible: boolean; score: number; available_beds: number; occupancy_pct: number; patient_count: number; reasons: string[]; blockers: string[]; }
export interface RoutingResult { patient_id: number; patient_code: string; disclaimer: string; weights: { availability: number; occupancy: number }; candidates: RoutingCandidate[]; }
export interface AIResult {
  execution_id: number; status: string; workflow: string; title: string; generated_at: string; engine: string; facts: Record<string, unknown>;
  recommendations: { priority: string; ref: string; text: string }[]; headline: string; ai_narrative: string | null; used_llm: boolean; warnings: string[]; disclaimer: string;
}
export interface AIExecution { id: number; workflow: string; status: string; input: unknown; output: { headline?: string } | null; error: string | null; used_llm: boolean; provider: string | null; started_at: string; finished_at: string | null; }
export type Settings = Record<string, number | boolean>;
