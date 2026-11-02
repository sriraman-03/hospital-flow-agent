import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { beds, departments, patients } from "@/api/endpoints";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { QueryBoundary } from "@/components/common/States";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useApiMutation } from "@/hooks/useApiMutation";
import { useAuth } from "@/hooks/useAuth";
import { cn, fmtDateTime } from "@/lib/utils";
import type { Bed } from "@/types";

const STATUSES = ["available", "occupied", "cleaning", "maintenance", "unavailable"];
const BED_TONE: Record<string, string> = {
  available: "border-emerald-500/60 bg-emerald-50 dark:bg-emerald-950/40", occupied: "border-sky-500/60 bg-sky-50 dark:bg-sky-950/40",
  cleaning: "border-amber-500/60 bg-amber-50 dark:bg-amber-950/40", maintenance: "border-red-500/60 bg-red-50 dark:bg-red-950/40", unavailable: "border-slate-400 bg-slate-100 dark:bg-slate-800/60",
};

function BedDialog({ bed, onClose }: { bed: Bed; onClose: () => void }) {
  const { can } = useAuth();
  const write = can("beds:write");
  const [patientId, setPatientId] = useState("");
  const [toBed, setToBed] = useState("");
  const candidates = useQuery({ queryKey: ["patients", "admitted", bed.department_id], enabled: write && bed.status === "available",
    queryFn: () => patients.list({ status: "admitted", department_id: bed.department_id, page_size: 200 }) });
  const freeBeds = useQuery({ queryKey: ["beds", "free", bed.department_id], enabled: write && bed.status === "occupied",
    queryFn: () => beds.list({ department_id: bed.department_id, status: "available", page_size: 200 }) });
  const assign = useApiMutation(() => beds.assign(bed.id, Number(patientId)), { success: `Bed ${bed.code} assigned`, onSuccess: onClose });
  const release = useApiMutation(() => beds.release(bed.id), { success: `Bed ${bed.code} released`, onSuccess: onClose });
  const move = useApiMutation(() => beds.move(bed.patient_id!, Number(toBed)), { success: "Patient moved", onSuccess: onClose });
  const setStatus = useApiMutation((s: string) => beds.setStatus(bed.id, s), { success: "Bed status updated", onSuccess: onClose });
  const unassigned = candidates.data?.items.filter((p) => !p.bed_id) ?? [];

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}><DialogContent>
      <DialogHeader><DialogTitle>Bed {bed.code}</DialogTitle><DialogDescription>{bed.department_name} · {bed.ward}</DialogDescription></DialogHeader>
      <div className="flex items-center gap-2 text-sm">Status: <StatusBadge status={bed.status} />{bed.patient_code && <Link className="text-primary hover:underline" to={`/patients/${bed.patient_id}`}>{bed.patient_code}</Link>}</div>
      {!write && <p className="text-sm text-muted-foreground">Your role has read-only access to beds.</p>}
      {write && bed.status === "available" && (
        <div className="grid gap-2 border-t pt-3">
          <FormField label="Assign admitted patient" htmlFor="bd-pt" hint={unassigned.length ? undefined : "No admitted patients without a bed in this department."}>
            <Select id="bd-pt" value={patientId} onChange={(e) => setPatientId(e.target.value)}><option value="">Select patient…</option>{unassigned.map((p) => <option key={p.id} value={p.id}>{p.patient_code} · {p.last_name}</option>)}</Select></FormField>
          <Button disabled={!patientId || assign.isPending} onClick={() => assign.mutate(undefined)}>Assign bed</Button>
        </div>
      )}
      {write && bed.status === "occupied" && (
        <div className="grid gap-3 border-t pt-3">
          <div className="grid gap-2"><FormField label="Move patient to another bed (same department)" htmlFor="bd-mv"><Select id="bd-mv" value={toBed} onChange={(e) => setToBed(e.target.value)}><option value="">Select bed…</option>{freeBeds.data?.items.map((b) => <option key={b.id} value={b.id}>{b.code} · {b.ward}</option>)}</Select></FormField>
            <Button variant="outline" disabled={!toBed || move.isPending} onClick={() => move.mutate(undefined)}>Move patient</Button></div>
          <Button variant="destructive" disabled={release.isPending} onClick={() => release.mutate(undefined)}>Release bed (patient stays admitted without a bed)</Button>
          <p className="text-xs text-muted-foreground">To release a bed after discharge, complete the discharge workflow; it releases the bed automatically.</p>
        </div>
      )}
      {write && bed.status !== "occupied" && (
        <div className="grid gap-2 border-t pt-3"><FormField label="Change bed status" htmlFor="bd-st">
          <Select id="bd-st" value={bed.status} onChange={(e) => setStatus.mutate(e.target.value)} disabled={setStatus.isPending}>{STATUSES.filter((s) => s !== "occupied").map((s) => <option key={s} value={s}>{s}</option>)}</Select></FormField></div>
      )}
      <DialogFooter><Button variant="outline" onClick={onClose}>Close</Button></DialogFooter>
    </DialogContent></Dialog>
  );
}

function NewBedDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const depts = useQuery({ queryKey: ["departments"], queryFn: departments.list });
  const [code, setCode] = useState(""), [dept, setDept] = useState(""), [ward, setWard] = useState("General");
  const m = useApiMutation(() => beds.create({ code: code.trim(), department_id: Number(dept), ward: ward.trim() || "General" }), { success: "Bed created", onSuccess: () => { setCode(""); onOpenChange(false); } });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}><DialogContent>
      <DialogHeader><DialogTitle>Add bed</DialogTitle></DialogHeader>
      <FormField label="Bed code *" htmlFor="nb-c"><Input id="nb-c" value={code} onChange={(e) => setCode(e.target.value)} maxLength={32} /></FormField>
      <FormField label="Department *" htmlFor="nb-d"><Select id="nb-d" value={dept} onChange={(e) => setDept(e.target.value)}><option value="">Select…</option>{depts.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select></FormField>
      <FormField label="Ward" htmlFor="nb-w"><Input id="nb-w" value={ward} onChange={(e) => setWard(e.target.value)} /></FormField>
      <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button disabled={!code.trim() || !dept || m.isPending} onClick={() => m.mutate(undefined)}>Create</Button></DialogFooter>
    </DialogContent></Dialog>
  );
}

export default function BedsPage() {
  const { can } = useAuth();
  const [sp, setSp] = useSearchParams();
  const [tab, setTab] = useState<"beds" | "history">("beds");
  const [sel, setSel] = useState<Bed | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [hp, setHp] = useState(1);
  const dept = sp.get("department_id") ?? "", status = sp.get("status") ?? "", highlight = Number(sp.get("highlight"));
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); setSp(n, { replace: true }); };
  const depts = useQuery({ queryKey: ["departments"], queryFn: departments.list });
  const list = useQuery({ queryKey: ["beds", "list", dept, status], queryFn: () => beds.list({ department_id: dept, status, page_size: 200 }), refetchInterval: 30000 });
  const hist = useQuery({ queryKey: ["beds", "history", hp], queryFn: () => beds.history({ page: hp, page_size: 20 }), enabled: tab === "history" });

  const groups = useMemo(() => {
    const m = new Map<string, Bed[]>();
    list.data?.items.forEach((b) => { const k = `${b.department_name} — ${b.ward}`; m.set(k, [...(m.get(k) ?? []), b]); });
    return [...m.entries()];
  }, [list.data]);

  return (
    <>
      <PageHeader title="Bed Management" description="Bed status by department and ward, assignments and history."
        actions={can("departments:write") && <Button onClick={() => setShowNew(true)}><Plus className="h-4 w-4" />Add bed</Button>} />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">{depts.data?.map((d) => (
        <Card key={d.id}><CardContent className="p-3"><div className="truncate text-xs text-muted-foreground">{d.name}</div><div className="text-lg font-semibold">{d.occupied_beds}/{d.total_beds} <span className="text-xs font-normal text-muted-foreground">occupied</span></div></CardContent></Card>))}</div>
      <div role="tablist" className="mb-3 flex gap-1 border-b">{(["beds", "history"] as const).map((t) => (
        <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={cn("-mb-px border-b-2 px-4 py-2 text-sm", tab === t ? "border-primary font-medium text-primary" : "border-transparent text-muted-foreground")}>{t === "beds" ? "Beds" : "Assignment history"}</button>))}</div>
      {tab === "beds" ? <>
        <div className="mb-3 flex flex-wrap gap-2">
          <Select className="w-52" aria-label="Filter by department" value={dept} onChange={(e) => set("department_id", e.target.value)}><option value="">All departments</option>{depts.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select>
          <Select className="w-44" aria-label="Filter by status" value={status} onChange={(e) => set("status", e.target.value)}><option value="">All statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}</Select>
        </div>
        <QueryBoundary q={list} empty={{ isEmpty: list.data?.total === 0, title: "No beds match these filters" }}>
          <div className="space-y-4">{groups.map(([name, items]) => (
            <Card key={name}><CardHeader><CardTitle>{name}</CardTitle></CardHeader><CardContent>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">{items.map((b) => (
                <button key={b.id} onClick={() => setSel(b)} aria-label={`Bed ${b.code}, ${b.status}${b.patient_code ? `, ${b.patient_code}` : ""}`}
                  className={cn("rounded-md border-2 p-2 text-left text-sm hover:shadow", BED_TONE[b.status], highlight === b.id && "ring-2 ring-primary")}>
                  <div className="font-medium">{b.code}</div><div className="text-xs capitalize">{b.status}</div><div className="truncate text-xs text-muted-foreground">{b.patient_code ?? "\u00a0"}</div></button>))}</div>
            </CardContent></Card>))}</div>
        </QueryBoundary>
      </> : (
        <Card><QueryBoundary q={hist} empty={{ isEmpty: hist.data?.total === 0, title: "No assignments yet" }}>
          <Table><THead><TR><TH>Bed</TH><TH>Patient</TH><TH>Assigned</TH><TH>Released</TH><TH>Reason</TH></TR></THead>
            <TBody>{hist.data?.items.map((a) => (<TR key={a.id}><TD>{a.bed_code}</TD><TD><Link className="text-primary hover:underline" to={`/patients/${a.patient_id}`}>{a.patient_code}</Link></TD><TD>{fmtDateTime(a.assigned_at)}</TD><TD>{a.released_at ? fmtDateTime(a.released_at) : <StatusBadge status="active" />}</TD><TD>{a.release_reason ?? "—"}</TD></TR>))}</TBody></Table>
          <Pagination data={hist.data} onPage={setHp} />
        </QueryBoundary></Card>
      )}
      {sel && <BedDialog bed={sel} onClose={() => setSel(null)} />}
      <NewBedDialog open={showNew} onOpenChange={setShowNew} />
    </>
  );
}
