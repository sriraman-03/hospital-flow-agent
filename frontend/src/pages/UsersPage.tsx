import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { admin, departments } from "@/api/endpoints";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { QueryBoundary } from "@/components/common/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useApiMutation } from "@/hooks/useApiMutation";
import { useAuth } from "@/hooks/useAuth";
import { fmtDateTime, humanize } from "@/lib/utils";
import type { User } from "@/types";

const ROLES = ["administrator", "operations_staff", "department_staff", "viewer"];
const createSchema = z.object({ email: z.string().email(), full_name: z.string().trim().min(1).max(120), password: z.string().min(10, "At least 10 characters").max(72), role: z.enum(["administrator", "operations_staff", "department_staff", "viewer"]), department_id: z.string().optional() });

function CreateDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const depts = useQuery({ queryKey: ["departments"], queryFn: departments.list, enabled: open });
  const { register, handleSubmit, reset, formState: { errors } } = useForm<z.infer<typeof createSchema>>({ resolver: zodResolver(createSchema), defaultValues: { role: "viewer" } });
  const m = useApiMutation((v: z.infer<typeof createSchema>) => admin.createUser({ ...v, department_id: v.department_id ? Number(v.department_id) : null }), { invalidate: ["users", "audit"], success: "User created", onSuccess: () => { reset(); onOpenChange(false); } });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}><DialogContent>
      <DialogHeader><DialogTitle>New user</DialogTitle></DialogHeader>
      <form className="grid gap-3" onSubmit={handleSubmit((v) => m.mutate(v))}>
        <FormField label="Full name *" htmlFor="uf" error={errors.full_name?.message}><Input id="uf" {...register("full_name")} /></FormField>
        <FormField label="Email *" htmlFor="ue" error={errors.email?.message}><Input id="ue" type="email" autoComplete="off" {...register("email")} /></FormField>
        <FormField label="Initial password *" htmlFor="up" error={errors.password?.message} hint="Share securely; the user should change it after first sign-in."><Input id="up" type="password" autoComplete="new-password" {...register("password")} /></FormField>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Role" htmlFor="ur"><Select id="ur" {...register("role")}>{ROLES.map((r) => <option key={r} value={r}>{humanize(r)}</option>)}</Select></FormField>
          <FormField label="Department" htmlFor="ud"><Select id="ud" {...register("department_id")}><option value="">None</option>{depts.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select></FormField>
        </div>
        <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button type="submit" disabled={m.isPending}>Create</Button></DialogFooter>
      </form>
    </DialogContent></Dialog>
  );
}

function ResetDialog({ u, onClose }: { u: User; onClose: () => void }) {
  const [pw, setPw] = useState("");
  const m = useApiMutation(() => admin.resetPassword(u.id, pw), { invalidate: ["audit"], success: "Password reset; the user's sessions were signed out", onSuccess: onClose });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}><DialogContent>
      <DialogHeader><DialogTitle>Reset password: {u.email}</DialogTitle></DialogHeader>
      <FormField label="New password (min 10 characters)" htmlFor="rp"><Input id="rp" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} /></FormField>
      <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button disabled={pw.length < 10 || m.isPending} onClick={() => m.mutate(undefined)}>Reset</Button></DialogFooter>
    </DialogContent></Dialog>
  );
}

export default function UsersPage() {
  const { user: me } = useAuth();
  const q = useQuery({ queryKey: ["users"], queryFn: admin.users });
  const [show, setShow] = useState(false);
  const [reset, setReset] = useState<User | null>(null);
  const update = useApiMutation(({ id, body }: { id: number; body: object }) => admin.updateUser(id, body), { invalidate: ["users", "audit"], success: "User updated" });
  return (
    <>
      <PageHeader title="User Management" description="Roles are enforced by the backend on every request." actions={<Button onClick={() => setShow(true)}><Plus className="h-4 w-4" />New user</Button>} />
      <Card><QueryBoundary q={q}>
        <Table><THead><TR><TH>Name</TH><TH>Email</TH><TH>Role</TH><TH>Status</TH><TH>Last sign-in</TH><TH><span className="sr-only">Actions</span></TH></TR></THead>
          <TBody>{q.data?.map((u) => (
            <TR key={u.id}><TD className="font-medium">{u.full_name}</TD><TD>{u.email}</TD>
              <TD><Select aria-label={`Role for ${u.email}`} className="w-44" value={u.role} disabled={u.id === me?.id || update.isPending} onChange={(e) => update.mutate({ id: u.id, body: { role: e.target.value } })}>{ROLES.map((r) => <option key={r} value={r}>{humanize(r)}</option>)}</Select></TD>
              <TD><Badge tone={u.is_active ? "success" : "neutral"}>{u.is_active ? "Active" : "Disabled"}</Badge></TD><TD>{fmtDateTime(u.last_login_at)}</TD>
              <TD><div className="flex justify-end gap-1"><Button size="sm" variant="outline" disabled={u.id === me?.id} onClick={() => update.mutate({ id: u.id, body: { is_active: !u.is_active } })}>{u.is_active ? "Disable" : "Enable"}</Button>
                <Button size="sm" variant="ghost" onClick={() => setReset(u)}>Reset password</Button></div></TD></TR>))}</TBody></Table>
      </QueryBoundary></Card>
      <CreateDialog open={show} onOpenChange={setShow} />
      {reset && <ResetDialog u={reset} onClose={() => setReset(null)} />}
    </>
  );
}
