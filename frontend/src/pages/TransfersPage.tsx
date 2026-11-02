import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { beds, departments, patients, transfers } from "@/api/endpoints";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { QueryBoundary } from "@/components/common/States";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, Textarea } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useApiMutation } from "@/hooks/useApiMutation";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";
import type { Transfer } from "@/types";
import { PatientLink, Times } from "./WorkflowShared";

function NewTransfer({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [pid, setPid] = useState(""), [dept, setDept] = useState(""), [bed, setBed] = useState(""), [reason, setReason] = useState("");
  const pts = useQuery({ queryKey: ["patients", "admitted-all"], queryFn: () => patients.list({ status: "admitted", page_size: 200 }), enabled: open });
  const depts = useQuery({ queryKey: ["departments"], queryFn: departments.list, enabled: open });
  const free = useQuery({ queryKey: ["beds", "free", dept], queryFn: () => beds.list({ department_id: dept, status: "available", page_size: 200 }), enabled: open && !!dept });
  const current = pts.data?.items.find((p) => String(p.id) === pid);
  const m = useApiMutation(() => transfers.create({ patient_id: Number(pid), destination_department_id: Number(dept), destination_bed_id: bed ? Number(bed) : null, reason: reason || null }), { success: "Transfer requested", onSuccess: () => { onOpenChange(false); setPid(""); setDept(""); setBed(""); setReason(""); } });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}><DialogContent>
      <DialogHeader><DialogTitle>Request transfer</DialogTitle></DialogHeader>
      <FormField label="Patient *" htmlFor="tp"><Select id="tp" value={pid} onChange={(e) => setPid(e.target.value)}><option value="">Select admitted patient…</option>{pts.data?.items.map((p) => <option key={p.id} value={p.id}>{p.patient_code} · {p.last_name} ({p.department_name})</option>)}</Select></FormField>
      <FormField label="Destination department *" htmlFor="td"><Select id="td" value={dept} onChange={(e) => { setDept(e.target.value); setBed(""); }}><option value="">Select…</option>{depts.data?.filter((d) => d.status !== "closed" && d.id !== current?.department_id).map((d) => <option key={d.id} value={d.id}>{d.name} ({d.available_beds} free)</option>)}</Select></FormField>
      <FormField label="Destination bed (optional)" htmlFor="tb"><Select id="tb" value={bed} onChange={(e) => setBed(e.target.value)} disabled={!dept}><option value="">Assign later</option>{free.data?.items.map((b) => <option key={b.id} value={b.id}>{b.code} · {b.ward}</option>)}</Select></FormField>
      <FormField label="Reason (operational)" htmlFor="tr"><Textarea id="tr" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} /></FormField>
      <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button disabled={!pid || !dept || m.isPending} onClick={() => m.mutate(undefined)}>Request transfer</Button></DialogFooter>
    </DialogContent></Dialog>
  );
}

export default function TransfersPage() {
  const { can } = useAuth();
  const [sp, setSp] = useSearchParams();
  const status = sp.get("status") ?? "", page = Number(sp.get("page") ?? 1), highlight = Number(sp.get("highlight"));
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); if (k !== "page") n.delete("page"); setSp(n, { replace: true }); };
  const list = useQuery({ queryKey: ["transfers", status, page], queryFn: () => transfers.list({ status, page, page_size: 20 }), placeholderData: (p) => p, refetchInterval: 30000 });
  const [show, setShow] = useState(false);
  const [cancel, setCancel] = useState<Transfer | null>(null);
  const act = useApiMutation(({ id, action }: { id: number; action: "approve" | "start" | "complete" }) => transfers.act(id, action), { success: (t) => `Transfer #${t.id} is now ${t.status.replace("_", " ")}` });
  const cancelM = useApiMutation(({ id, reason }: { id: number; reason: string }) => transfers.cancel(id, reason), { success: "Transfer cancelled", onSuccess: () => setCancel(null) });

  const actions = (t: Transfer) => (
    <div className="flex flex-wrap justify-end gap-1">
      {t.status === "requested" && can("transfers:approve") && <Button size="sm" disabled={act.isPending} onClick={() => act.mutate({ id: t.id, action: "approve" })}>Approve</Button>}
      {t.status === "approved" && can("transfers:write") && <Button size="sm" disabled={act.isPending} onClick={() => act.mutate({ id: t.id, action: "start" })}>Start</Button>}
      {t.status === "in_progress" && can("transfers:write") && <Button size="sm" disabled={act.isPending} onClick={() => act.mutate({ id: t.id, action: "complete" })}>Complete</Button>}
      {["requested", "approved", "in_progress"].includes(t.status) && can("transfers:write") && <Button size="sm" variant="outline" onClick={() => setCancel(t)}>Cancel</Button>}
    </div>
  );

  return (
    <>
      <PageHeader title="Transfers" description="Request, approve and complete inter-department transfers."
        actions={can("transfers:write") && <Button onClick={() => setShow(true)}><Plus className="h-4 w-4" />Request transfer</Button>} />
      <Card>
        <div className="border-b p-3"><Select className="w-48" aria-label="Filter by status" value={status} onChange={(e) => set("status", e.target.value)}><option value="">All statuses</option>{["requested", "approved", "in_progress", "completed", "cancelled"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</Select></div>
        <QueryBoundary q={list} empty={{ isEmpty: list.data?.total === 0, title: "No transfers", hint: "Requests appear here once created." }}>
          <Table><THead><TR><TH>#</TH><TH>Patient</TH><TH>From → To</TH><TH>Bed</TH><TH>Status</TH><TH>Timeline</TH><TH><span className="sr-only">Actions</span></TH></TR></THead>
            <TBody>{list.data?.items.map((t) => (
              <TR key={t.id} className={cn(highlight === t.id && "bg-accent")}>
                <TD>{t.id}</TD><TD><PatientLink id={t.patient_id} code={t.patient_code} /></TD><TD>{t.source_department_name ?? "—"} → <b>{t.destination_department_name}</b></TD><TD>{t.destination_bed_code ?? "—"}</TD>
                <TD><StatusBadge status={t.status} />{t.cancellation_reason && <div className="mt-1 max-w-48 text-xs text-muted-foreground">Reason: {t.cancellation_reason}</div>}</TD>
                <TD><Times items={[["Requested", t.requested_at], ["Approved", t.approved_at], ["Started", t.started_at], ["Completed", t.completed_at], ["Cancelled", t.cancelled_at]]} /></TD><TD>{actions(t)}</TD>
              </TR>))}</TBody></Table>
          <Pagination data={list.data} onPage={(n) => set("page", String(n))} />
        </QueryBoundary>
      </Card>
      <NewTransfer open={show} onOpenChange={setShow} />
      <ConfirmDialog open={!!cancel} onOpenChange={(o) => !o && setCancel(null)} title={`Cancel transfer #${cancel?.id}`} destructive confirmLabel="Cancel transfer"
        reason={{ label: "Cancellation reason", required: true, minLength: 3 }} pending={cancelM.isPending} onConfirm={(reason) => cancel && cancelM.mutate({ id: cancel.id, reason })} />
    </>
  );
}
