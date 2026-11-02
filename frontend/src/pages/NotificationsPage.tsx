import { useQuery } from "@tanstack/react-query";
import { Check, CheckCheck, Eye, EyeOff, ExternalLink } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { notifications } from "@/api/endpoints";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { QueryBoundary } from "@/components/common/States";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { useApiMutation } from "@/hooks/useApiMutation";
import { useAuth } from "@/hooks/useAuth";
import { useDebounce } from "@/hooks/useDebounce";
import { cn, entityLink, fmtDateTime, humanize, timeAgo } from "@/lib/utils";
import type { Notification } from "@/types";

const CATEGORIES = ["patient", "bed", "resource", "routing", "transfer", "discharge", "ai", "system"];

export default function NotificationsPage() {
  const { can } = useAuth();
  const manage = can("notifications:manage");
  const [sp, setSp] = useSearchParams();
  const g = (k: string) => sp.get(k) ?? "";
  const q = g("q"), page = Number(g("page") || 1);
  const dq = useDebounce(q);
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); if (k !== "page") n.delete("page"); setSp(n, { replace: true }); };
  const params = { q: dq, category: g("category"), severity: g("severity"), is_read: g("is_read"), is_resolved: g("is_resolved"),
    date_from: g("date_from") ? `${g("date_from")}T00:00:00` : "", date_to: g("date_to") ? `${g("date_to")}T23:59:59` : "", page, page_size: 20 };
  const list = useQuery({ queryKey: ["notifications", params], queryFn: () => notifications.list(params), placeholderData: (p) => p, refetchInterval: 15000 });
  const [resolving, setResolving] = useState<Notification | null>(null);

  const read = useApiMutation(({ id, read }: { id: number; read: boolean }) => notifications.setRead(id, read));
  const readAll = useApiMutation(() => notifications.readAll(), { success: (r) => `${r.updated} notification(s) marked as read` });
  const ack = useApiMutation((id: number) => notifications.acknowledge(id), { success: "Alert acknowledged" });
  const resolve = useApiMutation(({ id, note }: { id: number; note: string }) => notifications.resolve(id, note), { success: "Alert resolved", onSuccess: () => setResolving(null) });

  return (
    <>
      <PageHeader title="Notifications & Alerts" description="Persistent, event-driven alerts. Marking as read does not resolve the underlying issue."
        actions={manage && <Button variant="outline" onClick={() => readAll.mutate(undefined)} disabled={readAll.isPending}><CheckCheck className="h-4 w-4" />Mark all as read</Button>} />
      <Card>
        <div className="grid gap-2 border-b p-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          <Input placeholder="Search…" aria-label="Search notifications" value={q} onChange={(e) => set("q", e.target.value)} className="xl:col-span-2" />
          <Select aria-label="Category" value={g("category")} onChange={(e) => set("category", e.target.value)}><option value="">All categories</option>{CATEGORIES.map((c) => <option key={c} value={c}>{humanize(c)}</option>)}</Select>
          <Select aria-label="Severity" value={g("severity")} onChange={(e) => set("severity", e.target.value)}><option value="">All severities</option>{["critical", "warning", "info", "success"].map((c) => <option key={c} value={c}>{humanize(c)}</option>)}</Select>
          <Select aria-label="Read status" value={g("is_read")} onChange={(e) => set("is_read", e.target.value)}><option value="">Read & unread</option><option value="false">Unread</option><option value="true">Read</option></Select>
          <Select aria-label="Resolution status" value={g("is_resolved")} onChange={(e) => set("is_resolved", e.target.value)}><option value="">Open & resolved</option><option value="false">Open</option><option value="true">Resolved</option></Select>
          <div className="flex items-center gap-1 sm:col-span-2 lg:col-span-2 xl:col-span-2"><Input type="date" aria-label="From date" value={g("date_from")} onChange={(e) => set("date_from", e.target.value)} /><span className="text-muted-foreground">–</span><Input type="date" aria-label="To date" value={g("date_to")} onChange={(e) => set("date_to", e.target.value)} /></div>
        </div>
        <QueryBoundary q={list} empty={{ isEmpty: list.data?.total === 0, title: "No notifications match", hint: "Try clearing some filters." }}>
          <ul className="divide-y">{list.data?.items.map((n) => {
            const link = entityLink(n.entity_type, n.entity_id);
            return (
              <li key={n.id} className={cn("flex flex-col gap-2 p-3 md:flex-row md:items-start", !n.is_read && "bg-accent/40")}>
                <div className="flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={n.severity} /><Badge tone="outline">{humanize(n.category)}</Badge>
                    {!n.is_read && <span className="h-2 w-2 rounded-full bg-primary" role="img" aria-label="Unread" />}
                    {n.is_acknowledged && <Badge tone="info">Acknowledged</Badge>}{n.is_resolved ? <Badge tone="success">Resolved</Badge> : <Badge tone="warning">Open</Badge>}
                  </div>
                  <div className={cn("text-sm", !n.is_read && "font-semibold")}>{n.title}</div>
                  <div className="text-sm text-muted-foreground">{n.description}</div>
                  {n.resolution_note && <div className="text-xs">Resolution note: {n.resolution_note}</div>}
                  <div className="text-xs text-muted-foreground" title={fmtDateTime(n.created_at)}>{timeAgo(n.created_at)} · {fmtDateTime(n.created_at)}{n.entity_type && ` · ${humanize(n.entity_type)} #${n.entity_id}`}</div>
                </div>
                <div className="flex flex-wrap gap-1 md:justify-end">
                  {link && <Button asChild size="sm" variant="ghost"><Link to={link}><ExternalLink className="h-3.5 w-3.5" />Open</Link></Button>}
                  {manage && <Button size="sm" variant="ghost" onClick={() => read.mutate({ id: n.id, read: !n.is_read })} disabled={read.isPending}>{n.is_read ? <><EyeOff className="h-3.5 w-3.5" />Unread</> : <><Eye className="h-3.5 w-3.5" />Read</>}</Button>}
                  {manage && !n.is_resolved && !n.is_acknowledged && <Button size="sm" variant="outline" onClick={() => ack.mutate(n.id)} disabled={ack.isPending}>Acknowledge</Button>}
                  {manage && !n.is_resolved && <Button size="sm" onClick={() => setResolving(n)}><Check className="h-3.5 w-3.5" />Resolve</Button>}
                </div>
              </li>);
          })}</ul>
          <Pagination data={list.data} onPage={(n) => set("page", String(n))} />
        </QueryBoundary>
      </Card>
      <ConfirmDialog open={!!resolving} onOpenChange={(o) => !o && setResolving(null)} title="Resolve alert" confirmLabel="Resolve"
        description={`"${resolving?.title}" will be closed. If the underlying condition persists, a new alert is raised by the next related event.`}
        reason={{ label: "Resolution note" }} pending={resolve.isPending} onConfirm={(note) => resolving && resolve.mutate({ id: resolving.id, note })} />
    </>
  );
}
