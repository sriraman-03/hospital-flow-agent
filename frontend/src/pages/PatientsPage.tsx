import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { departments, patients } from "@/api/endpoints";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { QueryBoundary } from "@/components/common/States";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useApiMutation } from "@/hooks/useApiMutation";
import { useAuth } from "@/hooks/useAuth";
import { useDebounce } from "@/hooks/useDebounce";
import { fmtDate, fmtDateTime } from "@/lib/utils";

const schema = z.object({
  first_name: z.string().trim().min(1, "Required").max(80),
  last_name: z.string().trim().min(1, "Required").max(80),
  date_of_birth: z.string().min(1, "Required").refine((d) => new Date(d) <= new Date(), "Cannot be in the future"),
  phone: z.string().max(32).optional(),
});
type Form = z.infer<typeof schema>;
export const PATIENT_STATUSES = ["registered", "pending_admission", "admitted", "discharge_pending", "discharged"];

export function RegisterPatientDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { register, handleSubmit, reset, formState: { errors } } = useForm<Form>({ resolver: zodResolver(schema) });
  const m = useApiMutation((v: Form) => patients.create({ ...v, phone: v.phone || null }), { success: (p) => `Patient ${p.patient_code} registered`, onSuccess: () => { reset(); onOpenChange(false); } });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Register patient</DialogTitle></DialogHeader>
        <form className="grid gap-3" onSubmit={handleSubmit((v) => m.mutate(v))}>
          <p className="text-xs text-muted-foreground">Use synthetic demo data only. An internal patient ID is generated automatically.</p>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="First name *" htmlFor="fn" error={errors.first_name?.message}><Input id="fn" {...register("first_name")} /></FormField>
            <FormField label="Last name *" htmlFor="ln" error={errors.last_name?.message}><Input id="ln" {...register("last_name")} /></FormField>
          </div>
          <FormField label="Date of birth *" htmlFor="dob" error={errors.date_of_birth?.message}><Input id="dob" type="date" max={new Date().toISOString().slice(0, 10)} {...register("date_of_birth")} /></FormField>
          <FormField label="Phone (optional)" htmlFor="ph" error={errors.phone?.message}><Input id="ph" type="tel" {...register("phone")} /></FormField>
          <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button type="submit" disabled={m.isPending}>{m.isPending ? "Saving…" : "Register"}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function PatientsPage() {
  const { can } = useAuth();
  const [sp, setSp] = useSearchParams();
  const [showNew, setShowNew] = useState(false);
  const q = sp.get("q") ?? "", status = sp.get("status") ?? "", dept = sp.get("department_id") ?? "";
  const sort = sp.get("sort") ?? "created_at", order = sp.get("order") ?? "desc", page = Number(sp.get("page") ?? 1);
  const dq = useDebounce(q);
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); if (k !== "page") n.delete("page"); setSp(n, { replace: true }); };
  const depts = useQuery({ queryKey: ["departments"], queryFn: departments.list });
  const list = useQuery({ queryKey: ["patients", "list", dq, status, dept, sort, order, page], queryFn: () => patients.list({ q: dq, status, department_id: dept, sort, order, page, page_size: 20 }), placeholderData: (p) => p });

  return (
    <>
      <PageHeader title="Patients" description="Registration, admission status and location. Operational data only."
        actions={can("patients:write") && <Button onClick={() => setShowNew(true)}><Plus className="h-4 w-4" />Register patient</Button>} />
      <Card>
        <div className="flex flex-wrap gap-2 border-b p-3">
          <Input className="w-full sm:w-64" placeholder="Search ID or name…" aria-label="Search patients" value={q} onChange={(e) => set("q", e.target.value)} />
          <Select className="w-44" aria-label="Filter by status" value={status} onChange={(e) => set("status", e.target.value)}><option value="">All statuses</option>{PATIENT_STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}</Select>
          <Select className="w-48" aria-label="Filter by department" value={dept} onChange={(e) => set("department_id", e.target.value)}><option value="">All departments</option>{depts.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select>
          <Select className="w-40" aria-label="Sort by" value={sort} onChange={(e) => set("sort", e.target.value)}>
            <option value="created_at">Newest registered</option><option value="last_name">Last name</option><option value="patient_code">Patient ID</option><option value="admitted_at">Admission time</option><option value="status">Status</option></Select>
          <Select className="w-28" aria-label="Sort order" value={order} onChange={(e) => set("order", e.target.value)}><option value="desc">Desc</option><option value="asc">Asc</option></Select>
        </div>
        <QueryBoundary q={list} empty={{ isEmpty: list.data?.total === 0, title: "No patients found", hint: "Adjust the filters or register a new patient." }}>
          <Table>
            <THead><TR><TH>Patient ID</TH><TH>Name</TH><TH>Date of birth</TH><TH>Status</TH><TH>Department</TH><TH>Bed</TH><TH>Admitted</TH></TR></THead>
            <TBody>{list.data?.items.map((p) => (
              <TR key={p.id}>
                <TD><Link className="font-medium text-primary hover:underline" to={`/patients/${p.id}`}>{p.patient_code}</Link></TD>
                <TD>{p.last_name}, {p.first_name}</TD><TD>{fmtDate(p.date_of_birth)}</TD><TD><StatusBadge status={p.status} /></TD>
                <TD>{p.department_name ?? "—"}</TD><TD>{p.bed_code ?? "—"}</TD><TD>{fmtDateTime(p.admitted_at)}</TD>
              </TR>))}</TBody>
          </Table>
          <Pagination data={list.data} onPage={(n) => set("page", String(n))} />
        </QueryBoundary>
      </Card>
      <RegisterPatientDialog open={showNew} onOpenChange={setShowNew} />
    </>
  );
}
