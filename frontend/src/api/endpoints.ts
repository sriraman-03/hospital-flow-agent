import type * as T from "@/types";
import { get, patch, post, put } from "./client";

type Q = Record<string, string | number | boolean | null | undefined>;

export const auth = {
  login: (email: string, password: string) => post<{ access_token: string; user: T.Me }>("/auth/login", { email, password }),
  logout: () => post("/auth/logout"),
  me: () => get<T.Me>("/auth/me"),
  changePassword: (current_password: string, new_password: string) => post("/auth/change-password", { current_password, new_password }),
};
export const dashboard = {
  summary: () => get<T.DashboardSummary>("/dashboard/summary"),
  analytics: (days = 14) => get<T.Analytics>("/dashboard/analytics", { days }),
};
export const patients = {
  list: (q: Q) => get<T.Page<T.Patient>>("/patients", q),
  get: (id: number) => get<T.Patient>(`/patients/${id}`),
  create: (b: unknown) => post<T.Patient>("/patients", b),
  update: (id: number, b: unknown) => patch<T.Patient>(`/patients/${id}`, b),
  requestAdmission: (id: number, department_id: number) => post<T.Patient>(`/patients/${id}/request-admission`, { department_id }),
  admit: (id: number, b: { department_id?: number | null; bed_id?: number | null }) => post<T.Patient>(`/patients/${id}/admit`, b),
  history: (id: number) => get<T.HistoryEvent[]>(`/patients/${id}/history`),
};
export const departments = {
  list: () => get<T.Department[]>("/departments"),
  create: (b: unknown) => post<T.Department>("/departments", b),
  update: (id: number, b: unknown) => patch<T.Department>(`/departments/${id}`, b),
};
export const beds = {
  list: (q: Q) => get<T.Page<T.Bed>>("/beds", q),
  create: (b: unknown) => post<T.Bed>("/beds", b),
  setStatus: (id: number, status: string) => patch<T.Bed>(`/beds/${id}/status`, { status }),
  assign: (id: number, patient_id: number) => post<T.Assignment>(`/beds/${id}/assign`, { patient_id }),
  release: (id: number) => post<T.Bed>(`/beds/${id}/release`, { reason: "manual" }),
  move: (patient_id: number, to_bed_id: number) => post<T.Assignment>("/beds/transfer-bed", { patient_id, to_bed_id }),
  history: (q: Q) => get<T.Page<T.Assignment>>("/beds/assignments", q),
};
export const resources = {
  list: (q: Q) => get<T.Page<T.Resource>>("/resources", q),
  create: (b: unknown) => post<T.Resource>("/resources", b),
  update: (id: number, b: unknown) => patch<T.Resource>(`/resources/${id}`, b),
  move: (id: number, b: { movement_type: string; quantity: number; reason?: string }) => post<T.Movement>(`/resources/${id}/movements`, b),
  movements: (id: number, q: Q) => get<T.Page<T.Movement>>(`/resources/${id}/movements`, q),
};
export const routing = {
  recommend: (patient_id: number, required_resource_ids: number[]) => post<T.RoutingResult>("/routing/recommendations", { patient_id, required_resource_ids }),
  confirm: (b: unknown) => post<{ action: string; transfer_id?: number }>("/routing/confirm", b),
};
export const transfers = {
  list: (q: Q) => get<T.Page<T.Transfer>>("/transfers", q),
  create: (b: unknown) => post<T.Transfer>("/transfers", b),
  act: (id: number, action: "approve" | "start" | "complete") => post<T.Transfer>(`/transfers/${id}/${action}`),
  cancel: (id: number, reason: string) => post<T.Transfer>(`/transfers/${id}/cancel`, { reason }),
};
export const discharges = {
  list: (q: Q) => get<T.Page<T.Discharge>>("/discharges", q),
  create: (patient_id: number, notes?: string) => post<T.Discharge>("/discharges", { patient_id, notes }),
  act: (id: number, action: "approve" | "complete") => post<T.Discharge>(`/discharges/${id}/${action}`),
  cancel: (id: number, reason: string) => post<T.Discharge>(`/discharges/${id}/cancel`, { reason }),
};
export const notifications = {
  list: (q: Q) => get<T.Page<T.Notification>>("/notifications", q),
  unread: () => get<T.UnreadCounts>("/notifications/unread-count"),
  setRead: (id: number, read: boolean) => post<T.Notification>(`/notifications/${id}/${read ? "read" : "unread"}`),
  readAll: () => post<{ updated: number }>("/notifications/read-all"),
  acknowledge: (id: number) => post<T.Notification>(`/notifications/${id}/acknowledge`),
  resolve: (id: number, note?: string) => post<T.Notification>(`/notifications/${id}/resolve`, { note: note || null }),
};
export const ai = {
  status: () => get<{ llm: { provider: string; configured: boolean; model: string | null }; workflows: Record<string, string>; note: string }>("/ai/status"),
  run: (workflow: string, extra: { patient_id?: number; question?: string } = {}) => post<T.AIResult>("/ai/workflows/run", { workflow, ...extra }),
  executions: () => get<T.AIExecution[]>("/ai/executions"),
};
export const admin = {
  audit: (q: Q) => get<T.Page<T.AuditLog>>("/audit-logs", q),
  users: () => get<T.User[]>("/users"),
  createUser: (b: unknown) => post<T.User>("/users", b),
  updateUser: (id: number, b: unknown) => patch<T.User>(`/users/${id}`, b),
  resetPassword: (id: number, new_password: string) => post(`/users/${id}/reset-password`, { new_password }),
  settings: () => get<T.Settings>("/settings"),
  saveSettings: (values: T.Settings) => put<T.Settings>("/settings", { values }),
};
