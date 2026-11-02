import { Badge } from "@/components/ui/badge";
import { humanize } from "@/lib/utils";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";
const TONES: Record<string, Tone> = {
  // severity
  critical: "danger", warning: "warning", info: "info", success: "success",
  // patient / workflow
  registered: "neutral", pending_admission: "warning", admitted: "success", discharge_pending: "warning", discharged: "neutral",
  requested: "info", approved: "success", in_progress: "warning", completed: "success", cancelled: "neutral",
  // beds
  available: "success", occupied: "info", cleaning: "warning", maintenance: "danger", unavailable: "neutral",
  // departments / resources
  active: "success", limited: "warning", closed: "danger", ok: "success", low: "warning", failed: "danger", running: "info",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={TONES[status] ?? "neutral"}>{humanize(status)}</Badge>;
}
