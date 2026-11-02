import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, ShieldAlert, XCircle } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { patients, resources, routing } from "@/api/endpoints";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { useApiMutation } from "@/hooks/useApiMutation";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/useToast";
import type { RoutingCandidate, RoutingResult } from "@/types";

export default function RoutingPage() {
  const { can } = useAuth();
  const toast = useToast();
  const [sp] = useSearchParams();
  const [patientId, setPatientId] = useState(sp.get("patient") ?? "");
  const [required, setRequired] = useState<number[]>([]);
  const [result, setResult] = useState<RoutingResult | null>(null);
  const [pick, setPick] = useState<RoutingCandidate | null>(null);

  const pts = useQuery({ queryKey: ["patients", "routable"], queryFn: async () => {
    const [a, b, c] = await Promise.all(["admitted", "registered", "pending_admission"].map((status) => patients.list({ status, page_size: 200 })));
    return [...a.items, ...c.items, ...b.items];
  } });
  const res = useQuery({ queryKey: ["resources", "all-active"], queryFn: () => resources.list({ page_size: 200 }) });
  const recommend = useMutation({ mutationFn: () => routing.recommend(Number(patientId), required), onSuccess: setResult, onError: (e) => toast.error((e as Error).message) });
  const confirm = useApiMutation((reason: string) => routing.confirm({ patient_id: Number(patientId), department_id: pick!.department_id, reason: reason || null, required_resource_ids: required }),
    { success: (r) => r.action === "transfer_requested" ? `Transfer #${r.transfer_id} requested. It still needs approval.` : "Admission requested", onSuccess: () => { setPick(null); setResult(null); } });
  const selected = pts.data?.find((p) => String(p.id) === patientId);

  return (
    <>
      <PageHeader title="Patient Routing" description="Capacity-based department suggestions. Staff review and confirm every action." />
      <div role="note" className="mb-4 flex items-start gap-2 rounded-md border border-warning/50 bg-amber-50 p-3 text-sm dark:bg-amber-950/30">
        <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
        <span>Suggestions use bed availability, capacity, pending transfers and optional resource rules only. They are <b>not clinical decisions</b>; clinical suitability must be assessed by qualified staff.</span>
      </div>
      <Card className="mb-4"><CardContent className="grid gap-4 p-4 md:grid-cols-2">
        <FormField label="Patient" htmlFor="rt-p"><Select id="rt-p" value={patientId} onChange={(e) => { setPatientId(e.target.value); setResult(null); }}>
          <option value="">Select patient…</option>{pts.data?.map((p) => <option key={p.id} value={p.id}>{p.patient_code} · {p.last_name} ({p.status.replace(/_/g, " ")}{p.department_name ? `, ${p.department_name}` : ""})</option>)}</Select></FormField>
        <fieldset className="grid gap-1.5"><legend className="text-sm font-medium">Required resources (optional)</legend>
          <div className="max-h-28 space-y-1 overflow-y-auto rounded-md border p-2">{res.data?.items.map((r) => (
            <label key={r.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={required.includes(r.id)} onChange={(e) => setRequired((x) => e.target.checked ? [...x, r.id] : x.filter((i) => i !== r.id))} />{r.name} <span className="text-xs text-muted-foreground">({r.department_name ?? "hospital-wide"})</span></label>))}</div></fieldset>
        <div><Button disabled={!patientId || recommend.isPending} onClick={() => recommend.mutate()}>{recommend.isPending ? "Evaluating…" : "Get recommendations"}</Button></div>
      </CardContent></Card>

      {result && <div className="space-y-3">
        <p className="text-sm text-muted-foreground">Recommendations for <b>{result.patient_code}</b>. Score weights: availability {result.weights.availability}, occupancy headroom {result.weights.occupancy} (configurable in Settings).</p>
        {result.candidates.map((c, i) => (
          <Card key={c.department_id} className={c.eligible ? "" : "opacity-80"}>
            <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
              <CardTitle className="flex items-center gap-2 text-base">{c.eligible ? <CheckCircle2 className="h-4 w-4 text-success" aria-hidden /> : <XCircle className="h-4 w-4 text-destructive" aria-hidden />}{c.department_name}
                {c.eligible && i === 0 && <Badge tone="success">Top suggestion</Badge>}{!c.eligible && <Badge tone="danger">Not eligible</Badge>}</CardTitle>
              <div className="flex items-center gap-3 text-sm">{c.eligible && <span>Score <b>{c.score}</b></span>}<span className="text-muted-foreground">{c.available_beds} beds free · {c.occupancy_pct}% occupied · {c.patient_count} patients</span>
                {c.eligible && can("transfers:write") && <Button size="sm" onClick={() => setPick(c)}>Review &amp; confirm…</Button>}</div>
            </CardHeader>
            <CardContent><ul className="list-disc space-y-0.5 pl-5 text-sm">{c.reasons.map((r, k) => <li key={`r${k}`}>{r}</li>)}{c.blockers.map((r, k) => <li key={`b${k}`} className="text-destructive">{r}</li>)}</ul></CardContent>
          </Card>))}
        <p className="text-xs text-muted-foreground">{result.disclaimer}</p>
      </div>}

      <ConfirmDialog open={!!pick} onOpenChange={(o) => !o && setPick(null)} title={`Confirm routing to ${pick?.department_name}`}
        description={selected?.status === "admitted" ? "This creates a transfer request. It must still be approved by authorised staff before the patient moves." : "This records a pending admission to the selected department."}
        reason={{ label: "Reason / notes" }} confirmLabel="Confirm routing" pending={confirm.isPending} onConfirm={(r) => confirm.mutate(r)} />
      {!can("transfers:write") && <p className="mt-4 text-sm text-muted-foreground">Your role can view recommendations but cannot confirm routing actions. <Link className="text-primary underline" to="/transfers">View transfers</Link></p>}
    </>
  );
}
