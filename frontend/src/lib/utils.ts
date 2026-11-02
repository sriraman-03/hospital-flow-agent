import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));

export const fmtDateTime = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—";
export const fmtDate = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" }) : "—");

export function timeAgo(iso: string): string {
  const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export const humanize = (s: string) => s.replace(/[_.]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export function entityLink(type?: string | null, id?: number | null): string | null {
  if (!type || !id) return null;
  switch (type) {
    case "patient": return `/patients/${id}`;
    case "bed": return `/beds?highlight=${id}`;
    case "resource": return `/resources?highlight=${id}`;
    case "transfer": return `/transfers?highlight=${id}`;
    case "discharge": return `/discharges?highlight=${id}`;
    case "department": return `/departments?highlight=${id}`;
    case "ai_workflow": return `/ai`;
    default: return null;
  }
}
