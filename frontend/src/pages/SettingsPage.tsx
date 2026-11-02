import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { admin, auth } from "@/api/endpoints";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { QueryBoundary } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useApiMutation } from "@/hooks/useApiMutation";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { useToast } from "@/hooks/useToast";
import type { Settings } from "@/types";

const LABELS: Record<string, { label: string; hint: string; kind: "bool" | "number" }> = {
  discharge_requires_approval: { label: "Discharges require approval", hint: "When off, requests are approved automatically.", kind: "bool" },
  occupancy_warning_pct: { label: "Occupancy warning threshold (%)", hint: "Raises a warning alert at or above this level.", kind: "number" },
  occupancy_critical_pct: { label: "Occupancy critical threshold (%)", hint: "Raises a critical alert at or above this level.", kind: "number" },
  routing_weight_availability: { label: "Routing weight: bed availability", hint: "0 to 1", kind: "number" },
  routing_weight_occupancy: { label: "Routing weight: occupancy headroom", hint: "0 to 1", kind: "number" },
};

export default function SettingsPage() {
  const { can, user, logout } = useAuth();
  const { dark, toggle } = useTheme();
  const toast = useToast();
  const q = useQuery({ queryKey: ["settings"], queryFn: admin.settings });
  const [form, setForm] = useState<Settings>({});
  useEffect(() => { if (q.data) setForm(q.data); }, [q.data]);
  const edit = can("settings:manage");
  const save = useApiMutation(() => admin.saveSettings(form), { invalidate: ["settings", "audit"], success: "Settings saved" });
  const [cur, setCur] = useState(""), [next, setNext] = useState("");
  const pw = useApiMutation(() => auth.changePassword(cur, next), { invalidate: [], success: "Password changed. Please sign in again.", onSuccess: () => { setTimeout(() => logout(), 1200); } });

  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card><CardHeader><CardTitle>Operational rules</CardTitle></CardHeader><CardContent>
          <QueryBoundary q={q}>
            <div className="grid gap-3">{Object.entries(LABELS).map(([key, m]) => (
              <FormField key={key} label={m.label} htmlFor={key} hint={m.hint}>
                {m.kind === "bool" ? <input id={key} type="checkbox" className="h-4 w-4" disabled={!edit} checked={!!form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.checked })} />
                  : <Input id={key} type="number" step="any" disabled={!edit} value={String(form[key] ?? "")} onChange={(e) => setForm({ ...form, [key]: e.target.value === "" ? 0 : Number(e.target.value) })} />}
              </FormField>))}
              {edit ? <Button onClick={() => save.mutate(undefined)} disabled={save.isPending}>Save settings</Button> : <p className="text-sm text-muted-foreground">Only administrators can change these settings.</p>}
            </div>
          </QueryBoundary>
        </CardContent></Card>
        <div className="space-y-4">
          <Card><CardHeader><CardTitle>Appearance</CardTitle></CardHeader><CardContent><Button variant="outline" onClick={toggle}>Switch to {dark ? "light" : "dark"} theme</Button></CardContent></Card>
          <Card><CardHeader><CardTitle>Account: {user?.email}</CardTitle></CardHeader><CardContent className="grid gap-3">
            <FormField label="Current password" htmlFor="cp"><Input id="cp" type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} /></FormField>
            <FormField label="New password (min 10 characters)" htmlFor="np"><Input id="np" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} /></FormField>
            <Button disabled={!cur || next.length < 10 || pw.isPending} onClick={() => next.length >= 10 ? pw.mutate(undefined) : toast.error("Password too short")}>Change password</Button>
          </CardContent></Card>
        </div>
      </div>
    </>
  );
}
