import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { z } from "zod";
import { beds, departments, discharges, patients } from "@/api/endpoints";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { QueryBoundary } from "@/components/common/States";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/input";
import { useApiMutation } from "@/hooks/useApiMutation";
import { useAuth } from "@/hooks/useAuth";
import { fmtDate, fmtDateTime } from "@/lib/utils";
import type { Patient } from "@/types";

const editSchema = z.object({ first_name: z.string().trim().min(1), last_name: z.string().trim().min(1), date_of_birth: z.string().min(1), phone: z.string().max(32).optional() });

function EditDialog({ p, open, onOpenChange }: { p: Patient; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { register, handleSubmit, formState: { errors } } = useForm<z.infer<typeof editSchema>>({
    resolver: zodResolver(editSchema), defaultValues: { first_name: p.first_name, last_name: p.last_name, date_of_birth: p.date_of_birth, phone: p.phone ?? "" } });
  const m = useApiMutation((v: z.infer<typeof editSchema>) => patients.update(p.id, { ...v, phone: v.phone || null }), { success: "Patient updated", onSuccess: () => onOpenChange(false) });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}><DialogContent>
      <DialogHeader><DialogTitle>Edit patient {p.patient_code}</DialogTitle></DialogHeader>
      <form className="grid gap-3" onSubmit={handleSubmit((v) => m.mutate(v))}>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="First name" htmlFor="efn" error={errors.first_name?.message}><Input id="efn" {...register("first_name")} /></FormField>
          <FormField label="Last name" htmlFor="eln" error={errors.last_name?.message}><Input id="eln" {...register("last_name")} /></FormField>
        </div>
        <FormField label="Date of birth" htmlFor="edob" error={errors.date_of_birth?.message}><Input id="edob" type="date" {...register("date_of_birth")} /></FormField>
        <FormField label="Phone" htmlFor="eph"><Input id="eph" {...register("phone")} /></FormField>
        <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button type="submit" disabled={m.isPending}>Save</Button></DialogFooter>
      </form>
    </DialogContent></Dialog>
  );
}

function AdmitDialog({ p, open, onOpenChange }: { p: Patient; open: boolean; onOpenChange: (o: boolean) => void }) {
  const depts = useQuery({ queryKey: ["departments"], queryFn: departments.list });
  const [dept, setDept] = useState<string>(String(p.requested_department_id ?? ""));
  const [bed, setBed] = useState("");
  const freeBeds = useQuery({ queryKey: ["beds", "free", dept], queryFn: () => beds.list({ department_id: dept, status: "available", page_size: 200 }), enabled: !!dept });
  const m = useApiMutation(() => patients.admit(p.id, { department_id: Number(dept), bed_id: bed ? Number(bed) : null }), { success: "Patient admitted", onSuccess: () => onOpenChange(false) });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}><DialogContent>
      <DialogHeader><DialogTitle>Admit {p.patient_code}</DialogTitle></DialogHeader>
      <FormField label="Department *" htmlFor="ad-dept"><Select id="ad-dept" value={dept} onChange={(e) => { setDept(e.target.value); setBed(""); }}>
        <option value="">Select…</option>{depts.data?.filter((d) => d.status !== "closed").map((d) => <option key={d.id} value={d.id}>{d.name} ({d.available_beds} beds free)</option>)}</Select></FormField>
      <FormField label="Bed (optional)" htmlFor="ad-bed" hint="You can assign a bed later from Bed Management."><Select id="ad-bed" value={bed} onChange={(e) => setBed(e.target.value)} disabled={!dept}>
        <option value="">No bed yet</option>{freeBeds.data?.items.map((b) => <option key={b.id} value={b.id}>{b.code} · {b.ward}</option>)}</Select></FormField>
      <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button disabled={!dept || m.isPending} onClick={() => m.mutate(undefined)}>Admit patient</Button></DialogFooter>
    </DialogContent></Dialog>
  );
}

export default function PatientDetailPage() {
  const id = Number(useParams().id);
  const { can } = useAuth();
  const [edit, setEdit] = useState(false), [admit, setAdmit] = useState(false), [discharge, setDischarge] = useState(false);
  const q = useQuery({ queryKey: ["patients", id], queryFn: () => patients.get(id) });
  const hist = useQuery({ queryKey: ["patients", id, "history"], queryFn: () => patients.history(id) });
  const reqDischarge = useApiMutation((notes: string) => discharges.create(id, notes || undefined), { success: "Discharge requested", onSuccess: () => setDischarge(false) });
  const p = q.data;
  const canAdmit = p && ["registered", "pending_admission", "discharged"].includes(p.status);

  return (
    <>
      <Link to="/patients" className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"><ArrowLeft className="h-4 w-4" />Patients</Link>
      <QueryBoundary q={q}>{p && <>
        <PageHeader title={`${p.patient_code} · ${p.last_name}, ${p.first_name}`} actions={<>
          {can("patients:write") && <Button variant="outline" onClick={() => setEdit(true)}>Edit details</Button>}
          {can("patients:write") && canAdmit && <Button onClick={() => setAdmit(true)}>Admit</Button>}
          {can("transfers:write") && p.status === "admitted" && <Button variant="outline" asChild><Link to={`/routing?patient=${p.id}`}>Find / request transfer</Link></Button>}
          {can("discharges:write") && p.status === "admitted" && <Button variant="outline" onClick={() => setDischarge(true)}>Request discharge</Button>}
        </>} />
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-1"><CardHeader><CardTitle>Details</CardTitle></CardHeader><CardContent>
            <dl className="grid grid-cols-2 gap-y-2 text-sm">
              <dt className="text-muted-foreground">Status</dt><dd><StatusBadge status={p.status} /></dd>
              <dt className="text-muted-foreground">Date of birth</dt><dd>{fmtDate(p.date_of_birth)}</dd>
              <dt className="text-muted-foreground">Phone</dt><dd>{p.phone ?? "—"}</dd>
              <dt className="text-muted-foreground">Department</dt><dd>{p.department_name ?? "—"}</dd>
              <dt className="text-muted-foreground">Bed</dt><dd>{p.bed_code ?? "—"}</dd>
              <dt className="text-muted-foreground">Admitted</dt><dd>{fmtDateTime(p.admitted_at)}</dd>
              <dt className="text-muted-foreground">Discharged</dt><dd>{fmtDateTime(p.discharged_at)}</dd>
            </dl>
          </CardContent></Card>
          <Card className="lg:col-span-2"><CardHeader><CardTitle>Operational history</CardTitle></CardHeader><CardContent>
            <QueryBoundary q={hist} empty={{ isEmpty: hist.data?.length === 0, title: "No history yet" }}>
              <ol className="relative space-y-3 border-l pl-4">{hist.data?.map((e, i) => (
                <li key={i} className="text-sm"><span className="absolute -left-1 mt-1.5 h-2 w-2 rounded-full bg-primary" aria-hidden /><div>{e.description}</div><div className="text-xs text-muted-foreground">{fmtDateTime(e.timestamp)}</div></li>))}</ol>
            </QueryBoundary>
          </CardContent></Card>
        </div>
        {edit && <EditDialog p={p} open={edit} onOpenChange={setEdit} />}
        {admit && <AdmitDialog p={p} open={admit} onOpenChange={setAdmit} />}
        <ConfirmDialog open={discharge} onOpenChange={setDischarge} title={`Request discharge for ${p.patient_code}`} description="This starts the discharge workflow. A bed is released only when the discharge is completed."
          reason={{ label: "Operational notes" }} confirmLabel="Request discharge" pending={reqDischarge.isPending} onConfirm={(n) => reqDischarge.mutate(n)} />
      </>}</QueryBoundary>
    </>
  );
}
