import { Link } from "react-router-dom";
import { fmtDateTime } from "@/lib/utils";

export const PatientLink = ({ id, code }: { id: number; code: string }) => <Link className="font-medium text-primary hover:underline" to={`/patients/${id}`}>{code}</Link>;
export const Times = ({ items }: { items: [string, string | null | undefined][] }) => (
  <div className="space-y-0.5 text-xs text-muted-foreground">{items.filter(([, v]) => v).map(([k, v]) => <div key={k}>{k}: {fmtDateTime(v)}</div>)}</div>
);
