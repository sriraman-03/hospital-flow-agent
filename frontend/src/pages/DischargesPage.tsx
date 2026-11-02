import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { discharges, patients } from "@/api/endpoints";
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
import type { Discharge } from "@/types";
import { PatientLink, Times } from "./WorkflowShared";

function NewDischarge({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [pid, setPid] = useState(""), [notes, setNotes] = useState("");
  const pts = useQuery({ queryKey: ["patients", "admitted-all"], queryFn: () => patients.list({ status: "admitted", page_size: 200 }), enabled: open });
  const m = useApiMutation(() => discharges.create(Number(pid), notes || undefined), { success: "Discharge requested", onSuccess: () => { onOpenChange(false); setPid(""); setNotes(""); } });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}><DialogContent>
      <DialogHeader><DialogTitle>Request discharge</DialogTitle></DialogHeader>
      <FormField label="Patient *" htmlFor="dp"><Select id="dp" value={pid} onChange={(e) => setPid(e.target.value)}><option value="">Select admitted patient…</option>{pts.data?.items.map((p) => <option key={p.id} value={p.id}>{p.patient_code} · {p.last_name} ({p.department_name})</option>)}</Select></FormField>
      <FormField label="Operational notes" htmlFor="dn"><Textarea id="dn" value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500} /></FormField>
      <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button disabled={!pid || m.isPending} onClick={() => m.mutate(undefined)}>Request</Button></DialogFooter>
    </DialogContent></Dialog>
  );
}

export default function DischargesPage() {
  const { can } = useAuth();
  const [sp, setSp] = useSearchParams();
  const status = sp.get("status") ?? "", page = Number(sp.get("page") ?? 1), highlight = Number(sp.get("highlight"));
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); if (k !== "page") n.delete("page"); setSp(n, { replace: true }); };
  const list = useQuery({ queryKey: ["discharges", status, page], queryFn: () => discharges.list({ status, page, page_size: 20 }), placeholderData: (p) => p, refetchInterval: 30000 });
  const [show, setShow] = useState(false);
  const [cancel, setCancel] = useState<Discharge | null>(null);
  const [complete, setComplete] = useState<Discharge | null>(null);
  const act = useApiMutation(({ id, action }: { id: number; action: "approve" | "complete" }) => discharges.act(id, action), { success: (d) => d.status === "completed" ? "Discharge completed and bed released" : "Discharge approved", onSuccess: () => setComplete(null) });
  const cancelM = useApiMutation(({ id, reason }: { id: number; reason: string }) => discharges.cancel(id, reason), { success: "Discharge cancelled", onSuccess: () => setCancel(null) });

  return (
    <>
      <PageHeader title="Discharges" description="Request, approve and complete discharges. Completing a discharge releases the patient's bed."
        actions={can("discharges:write") && <Button onClick={() => setShow(true)}><Plus className="h-4 w-4" />Request discharge</Button>} />
      <Card>
        <div className="border-b p-3"><Select className="w-48" aria-label="Filter by status" value={status} onChange={(e) => set("status", e.target.value)}><option value="">All statuses</option>{["requested", "approved", "completed", "cancelled"].map((s) => <option key={s} value={s}>{s}</option>)}</Select></div>
        <QueryBoundary q={list} empty={{ isEmpty: list.data?.total === 0, title: "No discharges" }}>
          <Table><THead><TR><TH>#</TH><TH>Patient</TH><TH>Department</TH><TH>Status</TH><TH>Notes</TH><TH>Timeline</TH><TH><span className="sr-only">Actions</span></TH></TR></THead>
            <TBody>{list.data?.items.map((d) => (
              <TR key={d.id} className={cn(highlight === d.id && "bg-accent")}>
                <TD>{d.id}</TD><TD><PatientLink id={d.patient_id} code={d.patient_code} /></TD><TD>{d.department_name ?? "—"}</TD>
                <TD><StatusBadge status={d.status} /></TD><TD className="max-w-56 text-xs">{d.cancellation_reason ? `Cancelled: ${d.cancellation_reason}` : d.notes ?? "—"}</TD>
                <TD><Times items={[["Requested", d.requested_at], ["Approved", d.approved_at], ["Completed", d.completed_at], ["Cancelled", d.cancelled_at]]} /></TD>
                <TD><div className="flex flex-wrap justify-end gap-1">
                  {d.status === "requested" && can("discharges:approve") && <Button size="sm" disabled={act.isPending} onClick={() => act.mutate({ id: d.id, action: "approve" })}>Approve</Button>}
                  {d.status === "approved" && can("discharges:write") && <Button size="sm" onClick={() => setComplete(d)}>Complete</Button>}
                  {["requested", "approved"].includes(d.status) && can("discharges:write") && <Button size="sm" variant="outline" onClick={() => setCancel(d)}>Cancel</Button>}</div></TD>
              </TR>))}</TBody></Table>
          <Pagination data={list.data} onPage={(n) => set("page", String(n))} />
        </QueryBoundary>
      </Card>
      <NewDischarge open={show} onOpenChange={setShow} />
      <ConfirmDialog open={!!complete} onOpenChange={(o) => !o && setComplete(null)} title={`Complete discharge #${complete?.id}`} description="The patient will be marked discharged and their bed released for cleaning."
        confirmLabel="Complete discharge" pending={act.isPending} onConfirm={() => complete && act.mutate({ id: complete.id, action: "complete" })} />
      <ConfirmDialog open={!!cancel} onOpenChange={(o) => !o && setCancel(null)} title={`Cancel discharge #${cancel?.id}`} destructive confirmLabel="Cancel discharge"
        reason={{ label: "Cancellation reason", required: true, minLength: 3 }} pending={cancelM.isPending} onConfirm={(reason) => cancel && cancelM.mutate({ id: cancel.id, reason })} />
    </>
  );
}
