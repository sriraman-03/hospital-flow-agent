import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";
import { departments } from "@/api/endpoints";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { QueryBoundary } from "@/components/common/States";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Select, Textarea } from "@/components/ui/input";
import { useApiMutation } from "@/hooks/useApiMutation";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";
import type { Department } from "@/types";

const schema = z.object({
  name: z.string().trim().min(2, "At least 2 characters").max(100), code: z.string().trim().min(2).max(20),
  description: z.string().max(500).optional(), capacity: z.coerce.number().int().min(0), status: z.enum(["active", "limited", "closed"]),
});
type Form = z.infer<typeof schema>;

function DeptDialog({ dept, open, onOpenChange }: { dept?: Department; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { register, handleSubmit, reset, formState: { errors } } = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { name: "", code: "", description: "", capacity: 0, status: "active" } });
  useEffect(() => { if (open) reset(dept ? { name: dept.name, code: dept.code, description: dept.description ?? "", capacity: dept.capacity, status: dept.status as Form["status"] } : { name: "", code: "", description: "", capacity: 0, status: "active" }); }, [open, dept, reset]);
  const m = useApiMutation((v: Form) => dept ? departments.update(dept.id, { name: v.name, description: v.description, capacity: v.capacity, status: v.status }) : departments.create(v),
    { success: dept ? "Department updated" : "Department created", onSuccess: () => onOpenChange(false) });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}><DialogContent>
      <DialogHeader><DialogTitle>{dept ? `Edit ${dept.name}` : "New department"}</DialogTitle></DialogHeader>
      <form className="grid gap-3" onSubmit={handleSubmit((v) => m.mutate(v))}>
        <FormField label="Name *" htmlFor="dn" error={errors.name?.message}><Input id="dn" {...register("name")} /></FormField>
        <FormField label="Code *" htmlFor="dc" error={errors.code?.message} hint={dept ? "Code cannot be changed." : undefined}><Input id="dc" disabled={!!dept} {...register("code")} /></FormField>
        <FormField label="Description" htmlFor="dd"><Textarea id="dd" {...register("description")} /></FormField>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Patient capacity" htmlFor="dcap" hint="0 = limited only by beds" error={errors.capacity?.message}><Input id="dcap" type="number" min={0} {...register("capacity")} /></FormField>
          <FormField label="Operational status" htmlFor="dst"><Select id="dst" {...register("status")}><option value="active">Active</option><option value="limited">Limited</option><option value="closed">Closed</option></Select></FormField>
        </div>
        <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button type="submit" disabled={m.isPending}>Save</Button></DialogFooter>
      </form>
    </DialogContent></Dialog>
  );
}

export default function DepartmentsPage() {
  const { can } = useAuth();
  const q = useQuery({ queryKey: ["departments"], queryFn: departments.list, refetchInterval: 30000 });
  const [editing, setEditing] = useState<Department | undefined>();
  const [open, setOpen] = useState(false);
  const highlight = Number(useSearchParams()[0].get("highlight"));
  return (
    <>
      <PageHeader title="Departments" description="Capacity, bed availability and operational status."
        actions={can("departments:write") && <Button onClick={() => { setEditing(undefined); setOpen(true); }}><Plus className="h-4 w-4" />New department</Button>} />
      <QueryBoundary q={q} empty={{ isEmpty: q.data?.length === 0, title: "No departments yet" }}>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{q.data?.map((d) => (
          <Card key={d.id} className={cn(highlight === d.id && "ring-2 ring-primary")}>
            <CardHeader className="flex-row items-start justify-between"><div><CardTitle className="text-base">{d.name}</CardTitle><p className="text-xs text-muted-foreground">{d.code}</p></div><StatusBadge status={d.status} /></CardHeader>
            <CardContent>
              {d.description && <p className="mb-3 text-sm text-muted-foreground">{d.description}</p>}
              <div className="mb-1 flex justify-between text-xs"><span>Bed occupancy</span><span>{d.occupancy_pct}%</span></div>
              <div className="h-2 overflow-hidden rounded bg-muted" role="progressbar" aria-valuenow={d.occupancy_pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${d.name} occupancy`}>
                <div className={cn("h-full", d.occupancy_pct >= 95 ? "bg-destructive" : d.occupancy_pct >= 85 ? "bg-warning" : "bg-primary")} style={{ width: `${Math.min(100, d.occupancy_pct)}%` }} /></div>
              <dl className="mt-3 grid grid-cols-3 gap-2 text-center text-sm">
                <div><dd className="text-lg font-semibold">{d.patient_count}{d.capacity ? `/${d.capacity}` : ""}</dd><dt className="text-xs text-muted-foreground">Patients</dt></div>
                <div><dd className="text-lg font-semibold">{d.available_beds}/{d.total_beds}</dd><dt className="text-xs text-muted-foreground">Beds free</dt></div>
                <div><dd className={cn("text-lg font-semibold", d.low_stock_resources && "text-warning")}>{d.low_stock_resources}</dd><dt className="text-xs text-muted-foreground">Low stock</dt></div>
              </dl>
              {can("departments:write") && <Button variant="outline" size="sm" className="mt-3" onClick={() => { setEditing(d); setOpen(true); }}>Edit</Button>}
            </CardContent>
          </Card>))}</div>
      </QueryBoundary>
      <DeptDialog dept={editing} open={open} onOpenChange={setOpen} />
    </>
  );
}
