import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";
import { departments, resources } from "@/api/endpoints";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { QueryBoundary } from "@/components/common/States";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useApiMutation } from "@/hooks/useApiMutation";
import { useAuth } from "@/hooks/useAuth";
import { useDebounce } from "@/hooks/useDebounce";
import { cn, fmtDateTime } from "@/lib/utils";
import type { Resource } from "@/types";

const num = z.coerce.number().int().min(0, "Must be 0 or more");
const schema = z.object({
  name: z.string().trim().min(1, "Required").max(120), category: z.string().trim().min(1).max(60), unit: z.string().trim().min(1).max(20),
  quantity: num, min_threshold: num, critical_threshold: num, department_id: z.string().optional(), storage_location: z.string().trim().min(1).max(100),
}).refine((v) => v.critical_threshold <= v.min_threshold, { path: ["critical_threshold"], message: "Cannot exceed the minimum threshold" });
type Form = z.infer<typeof schema>;
const EMPTY: Form = { name: "", category: "General", unit: "units", quantity: 0, min_threshold: 0, critical_threshold: 0, department_id: "", storage_location: "Main Store" };

function ResourceDialog({ r, open, onOpenChange }: { r?: Resource; open: boolean; onOpenChange: (o: boolean) => void }) {
  const depts = useQuery({ queryKey: ["departments"], queryFn: departments.list });
  const { register, handleSubmit, reset, formState: { errors } } = useForm<Form>({ resolver: zodResolver(schema), defaultValues: EMPTY });
  useEffect(() => { if (open) reset(r ? { ...r, department_id: r.department_id ? String(r.department_id) : "" } : EMPTY); }, [open, r, reset]);
  const m = useApiMutation((v: Form) => {
    const body = { ...v, department_id: v.department_id ? Number(v.department_id) : null };
    if (r) { const { quantity, ...rest } = body; return resources.update(r.id, rest); }
    return resources.create(body);
  }, { success: r ? "Resource updated" : "Resource created", onSuccess: () => onOpenChange(false) });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}><DialogContent>
      <DialogHeader><DialogTitle>{r ? `Edit ${r.name}` : "New resource"}</DialogTitle></DialogHeader>
      <form className="grid gap-3" onSubmit={handleSubmit((v) => m.mutate(v))}>
        <FormField label="Name *" htmlFor="rn" error={errors.name?.message}><Input id="rn" {...register("name")} /></FormField>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Category" htmlFor="rc" error={errors.category?.message}><Input id="rc" {...register("category")} /></FormField>
          <FormField label="Unit" htmlFor="ru" error={errors.unit?.message}><Input id="ru" {...register("unit")} /></FormField>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <FormField label="Quantity" htmlFor="rq" error={errors.quantity?.message} hint={r ? "Use stock movements" : undefined}><Input id="rq" type="number" min={0} disabled={!!r} {...register("quantity")} /></FormField>
          <FormField label="Minimum (low)" htmlFor="rm" error={errors.min_threshold?.message}><Input id="rm" type="number" min={0} {...register("min_threshold")} /></FormField>
          <FormField label="Critical" htmlFor="rcr" error={errors.critical_threshold?.message}><Input id="rcr" type="number" min={0} {...register("critical_threshold")} /></FormField>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Department" htmlFor="rd"><Select id="rd" {...register("department_id")}><option value="">Hospital-wide</option>{depts.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select></FormField>
          <FormField label="Storage location" htmlFor="rl" error={errors.storage_location?.message}><Input id="rl" {...register("storage_location")} /></FormField>
        </div>
        <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button type="submit" disabled={m.isPending}>Save</Button></DialogFooter>
      </form>
    </DialogContent></Dialog>
  );
}

function MovementDialog({ r, onClose }: { r: Resource; onClose: () => void }) {
  const [type, setType] = useState("addition"), [qty, setQty] = useState(""), [reason, setReason] = useState("");
  const n = Number(qty);
  const invalid = !Number.isInteger(n) || n < 0 || (type !== "adjustment" && n <= 0) || (type === "deduction" && n > r.quantity) || (type === "adjustment" && !reason.trim());
  const m = useApiMutation(() => resources.move(r.id, { movement_type: type, quantity: n, reason: reason.trim() || undefined }), { success: "Stock updated", onSuccess: onClose });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}><DialogContent>
      <DialogHeader><DialogTitle>Stock movement: {r.name}</DialogTitle></DialogHeader>
      <p className="text-sm text-muted-foreground">Current quantity: <b>{r.quantity} {r.unit}</b></p>
      <FormField label="Type" htmlFor="mt"><Select id="mt" value={type} onChange={(e) => setType(e.target.value)}><option value="addition">Add stock</option><option value="deduction">Deduct stock</option><option value="adjustment">Adjust to exact quantity (stock count)</option></Select></FormField>
      <FormField label={type === "adjustment" ? "New quantity *" : "Quantity *"} htmlFor="mq" error={type === "deduction" && n > r.quantity ? "Cannot deduct more than the current stock" : undefined}><Input id="mq" type="number" min={0} value={qty} onChange={(e) => setQty(e.target.value)} /></FormField>
      <FormField label={type === "adjustment" ? "Reason *" : "Reason (optional)"} htmlFor="mr"><Textarea id="mr" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} /></FormField>
      <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button disabled={invalid || qty === "" || m.isPending} onClick={() => m.mutate(undefined)}>Apply</Button></DialogFooter>
    </DialogContent></Dialog>
  );
}

function HistoryDialog({ r, onClose }: { r: Resource; onClose: () => void }) {
  const [page, setPage] = useState(1);
  const q = useQuery({ queryKey: ["resources", r.id, "movements", page], queryFn: () => resources.movements(r.id, { page, page_size: 10 }) });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}><DialogContent className="max-w-2xl">
      <DialogHeader><DialogTitle>Movement history: {r.name}</DialogTitle></DialogHeader>
      <QueryBoundary q={q} empty={{ isEmpty: q.data?.total === 0, title: "No movements" }}>
        <Table><THead><TR><TH>When</TH><TH>Type</TH><TH>Change</TH><TH>Before → After</TH><TH>Reason</TH></TR></THead>
          <TBody>{q.data?.items.map((m) => (<TR key={m.id}><TD>{fmtDateTime(m.created_at)}</TD><TD className="capitalize">{m.movement_type}</TD><TD className={m.quantity_change < 0 ? "text-destructive" : "text-success"}>{m.quantity_change > 0 ? "+" : ""}{m.quantity_change}</TD><TD>{m.quantity_before} → {m.quantity_after}</TD><TD>{m.reason ?? "—"}</TD></TR>))}</TBody></Table>
        <Pagination data={q.data} onPage={setPage} />
      </QueryBoundary>
    </DialogContent></Dialog>
  );
}

export default function ResourcesPage() {
  const { can } = useAuth();
  const [sp, setSp] = useSearchParams();
  const q = sp.get("q") ?? "", category = sp.get("category") ?? "", level = sp.get("level") ?? "", dept = sp.get("department_id") ?? "", page = Number(sp.get("page") ?? 1), highlight = Number(sp.get("highlight"));
  const dq = useDebounce(q);
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); if (k !== "page") n.delete("page"); setSp(n, { replace: true }); };
  const depts = useQuery({ queryKey: ["departments"], queryFn: departments.list });
  const list = useQuery({ queryKey: ["resources", "list", dq, category, level, dept, page], queryFn: () => resources.list({ q: dq, category, level, department_id: dept, page, page_size: 20 }), placeholderData: (p) => p, refetchInterval: 30000 });
  const [edit, setEdit] = useState<Resource | undefined>(); const [open, setOpen] = useState(false);
  const [mv, setMv] = useState<Resource | null>(null); const [hist, setHist] = useState<Resource | null>(null);
  const write = can("resources:write");

  return (
    <>
      <PageHeader title="Resource Management" description="Inventory, thresholds and stock movements. Alerts are raised automatically when thresholds are crossed."
        actions={write && <Button onClick={() => { setEdit(undefined); setOpen(true); }}><Plus className="h-4 w-4" />New resource</Button>} />
      <Card>
        <div className="flex flex-wrap gap-2 border-b p-3">
          <Input className="w-full sm:w-60" placeholder="Search name or location…" aria-label="Search resources" value={q} onChange={(e) => set("q", e.target.value)} />
          <Input className="w-40" placeholder="Category" aria-label="Filter by category" value={category} onChange={(e) => set("category", e.target.value)} />
          <Select className="w-44" aria-label="Filter by stock level" value={level} onChange={(e) => set("level", e.target.value)}><option value="">All levels</option><option value="ok">OK</option><option value="low">Low</option><option value="critical">Critical</option></Select>
          <Select className="w-48" aria-label="Filter by department" value={dept} onChange={(e) => set("department_id", e.target.value)}><option value="">All departments</option>{depts.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select>
        </div>
        <QueryBoundary q={list} empty={{ isEmpty: list.data?.total === 0, title: "No resources found" }}>
          <Table><THead><TR><TH>Resource</TH><TH>Category</TH><TH>Quantity</TH><TH>Min / Critical</TH><TH>Level</TH><TH>Location</TH><TH>Updated</TH><TH><span className="sr-only">Actions</span></TH></TR></THead>
            <TBody>{list.data?.items.map((r) => (
              <TR key={r.id} className={cn(highlight === r.id && "bg-accent")}>
                <TD className="font-medium">{r.name}{r.department_name && <div className="text-xs font-normal text-muted-foreground">{r.department_name}</div>}</TD><TD>{r.category}</TD>
                <TD className="tabular-nums">{r.quantity} {r.unit}</TD><TD className="tabular-nums">{r.min_threshold} / {r.critical_threshold}</TD><TD><StatusBadge status={r.level} /></TD><TD>{r.storage_location}</TD><TD>{fmtDateTime(r.updated_at)}</TD>
                <TD><div className="flex justify-end gap-1">
                  {write && <Button size="sm" variant="outline" onClick={() => setMv(r)}>Stock</Button>}
                  <Button size="sm" variant="ghost" onClick={() => setHist(r)}>History</Button>
                  {write && <Button size="sm" variant="ghost" onClick={() => { setEdit(r); setOpen(true); }}>Edit</Button>}</div></TD>
              </TR>))}</TBody></Table>
          <Pagination data={list.data} onPage={(n) => set("page", String(n))} />
        </QueryBoundary>
      </Card>
      <ResourceDialog r={edit} open={open} onOpenChange={setOpen} />
      {mv && <MovementDialog r={mv} onClose={() => setMv(null)} />}
      {hist && <HistoryDialog r={hist} onClose={() => setHist(null)} />}
    </>
  );
}
