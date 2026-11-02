import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { dashboard } from "@/api/endpoints";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/States";
import { StatusBadge } from "@/components/common/StatusBadge";
import { useApiMutation } from "@/hooks/useApiMutation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { notifications } from "@/api/endpoints";
import { useAuth } from "@/hooks/useAuth";
import { entityLink, fmtDateTime, humanize, timeAgo } from "@/lib/utils";
import type { DashboardSummary } from "@/types";

const SEV_COLORS: Record<string, string> = { critical: "#dc2626", warning: "#d97706", info: "#0284c7", success: "#059669" };
const AXIS = { fontSize: 12, fill: "currentColor" };

function Metric({ label, value, to, tone }: { label: string; value: string | number; to?: string; tone?: "danger" | "warning" }) {
  const body = (
    <Card className={tone === "danger" ? "border-destructive/50" : tone === "warning" ? "border-warning/50" : ""}>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      </CardContent>
    </Card>
  );
  return to ? <Link to={to} className="block rounded-lg">{body}</Link> : body;
}

export default function DashboardPage() {
  const { can } = useAuth();
  const summary = useQuery({ queryKey: ["dashboard", "summary"], queryFn: dashboard.summary, refetchInterval: 30000 });
  const analytics = useQuery({ queryKey: ["dashboard", "analytics"], queryFn: () => dashboard.analytics(14), refetchInterval: 30000 });
  const ack = useApiMutation((id: number) => notifications.acknowledge(id), { success: "Alert acknowledged" });
  const s: DashboardSummary | undefined = summary.data;

  return (
    <>
      <PageHeader title="Operations Dashboard" description="Live figures calculated from hospital records." />
      {summary.isError ? <ErrorState error={summary.error} onRetry={() => summary.refetch()} /> : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {!s ? Array.from({ length: 11 }).map((_, i) => <Skeleton key={i} className="h-20" />) : <>
            <Metric label="Registered patients" value={s.total_patients} to="/patients" />
            <Metric label="Admitted patients" value={s.admitted_patients} to="/patients?status=admitted" />
            <Metric label="Available beds" value={s.available_beds} to="/beds?status=available" />
            <Metric label="Occupied beds" value={s.occupied_beds} to="/beds?status=occupied" />
            <Metric label="Bed occupancy" value={`${s.occupancy_rate}%`} tone={s.occupancy_rate >= 95 ? "danger" : s.occupancy_rate >= 85 ? "warning" : undefined} />
            <Metric label="Pending admissions" value={s.pending_admissions} to="/patients?status=pending_admission" />
            <Metric label="Pending transfers" value={s.pending_transfers} to="/transfers" />
            <Metric label="Discharges in progress" value={s.discharges_in_progress} to="/discharges" />
            <Metric label="Resources below minimum" value={s.low_stock_resources} to="/resources?level=low" tone={s.low_stock_resources ? "warning" : undefined} />
            <Metric label="Unread notifications" value={s.unread_notifications} to="/notifications?is_read=false" />
            <Metric label="Critical active alerts" value={s.critical_active_alerts} to="/notifications?severity=critical&is_resolved=false" tone={s.critical_active_alerts ? "danger" : undefined} />
          </>}
        </div>
      )}

      <Card className="mt-4">
        <CardHeader><CardTitle>Critical alerts</CardTitle></CardHeader>
        <CardContent>
          {analytics.isLoading ? <Skeleton className="h-16" /> : !analytics.data?.critical_alerts.length ? <p className="py-4 text-sm text-muted-foreground">No critical alerts are currently active.</p> : (
            <ul className="divide-y">
              {analytics.data.critical_alerts.map((a) => {
                const link = entityLink(a.entity_type, a.entity_id);
                return (
                  <li key={a.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                    <StatusBadge status="critical" />
                    <div className="min-w-0 flex-1"><div className="font-medium">{a.title}</div><div className="truncate text-muted-foreground">{a.description}</div></div>
                    <span className="text-xs text-muted-foreground" title={fmtDateTime(a.created_at)}>{timeAgo(a.created_at)}</span>
                    {a.entity_type && <span className="text-xs text-muted-foreground">{humanize(a.entity_type)} #{a.entity_id}</span>}
                    {link && <Button asChild variant="outline" size="sm"><Link to={link}>View</Link></Button>}
                    {can("notifications:manage") && !a.is_acknowledged && <Button size="sm" onClick={() => ack.mutate(a.id)} disabled={ack.isPending}>Acknowledge</Button>}
                    {a.is_acknowledged && <span className="text-xs text-success">Acknowledged</span>}
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card><CardHeader><CardTitle>Bed occupancy by department</CardTitle></CardHeader><CardContent className="h-72">
          {analytics.data && <ResponsiveContainer><BarChart data={analytics.data.occupancy_by_department}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="department" tick={AXIS} /><YAxis allowDecimals={false} tick={AXIS} /><Tooltip /><Legend />
            <Bar dataKey="occupied" stackId="a" fill="#0284c7" name="Occupied" /><Bar dataKey="cleaning" stackId="a" fill="#d97706" name="Cleaning" /><Bar dataKey="available" stackId="a" fill="#059669" name="Available" /><Bar dataKey="out_of_service" stackId="a" fill="#94a3b8" name="Out of service" /></BarChart></ResponsiveContainer>}
        </CardContent></Card>
        <Card><CardHeader><CardTitle>Admissions vs discharges (14 days)</CardTitle></CardHeader><CardContent className="h-72">
          {analytics.data && <ResponsiveContainer><LineChart data={analytics.data.admissions_vs_discharges}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="date" tick={AXIS} tickFormatter={(d: string) => d.slice(5)} /><YAxis allowDecimals={false} tick={AXIS} /><Tooltip /><Legend />
            <Line type="monotone" dataKey="admissions" stroke="#0284c7" name="Admissions" strokeWidth={2} dot={false} /><Line type="monotone" dataKey="discharges" stroke="#059669" name="Discharges" strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer>}
        </CardContent></Card>
        <Card><CardHeader><CardTitle>Resource inventory (lowest relative to minimum)</CardTitle></CardHeader><CardContent className="h-80">
          {analytics.data && <ResponsiveContainer><BarChart data={analytics.data.resource_levels} layout="vertical" margin={{ left: 40 }}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis type="number" tick={AXIS} /><YAxis type="category" dataKey="name" width={150} tick={AXIS} /><Tooltip /><Legend />
            <Bar dataKey="quantity" fill="#0284c7" name="Quantity" /><Bar dataKey="min_threshold" fill="#d97706" name="Minimum" /></BarChart></ResponsiveContainer>}
        </CardContent></Card>
        <Card><CardHeader><CardTitle>Active alerts by severity</CardTitle></CardHeader><CardContent className="h-80">
          {analytics.data && <ResponsiveContainer><BarChart data={analytics.data.alerts_by_severity.map((a) => ({ ...a, label: humanize(a.severity) }))}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="label" tick={AXIS} /><YAxis allowDecimals={false} tick={AXIS} /><Tooltip />
            <Bar dataKey="count" name="Active alerts">{analytics.data.alerts_by_severity.map((a) => <Cell key={a.severity} fill={SEV_COLORS[a.severity]} />)}</Bar></BarChart></ResponsiveContainer>}
        </CardContent></Card>
      </div>

      <Card className="mt-4">
        <CardHeader><CardTitle>Recent operational activity</CardTitle></CardHeader>
        <CardContent>
          {analytics.isLoading ? <Skeleton className="h-24" /> : !analytics.data?.recent_activity.length ? <p className="py-4 text-sm text-muted-foreground">No activity recorded yet.</p> : (
            <ul className="divide-y text-sm">{analytics.data.recent_activity.map((a) => (
              <li key={a.id} className="flex flex-wrap justify-between gap-2 py-2"><span><span className="font-medium">{humanize(a.action)}</span> <span className="text-muted-foreground">· {humanize(a.entity_type)}{a.entity_id ? ` #${a.entity_id}` : ""}</span></span>
                <span className="text-xs text-muted-foreground">{a.actor ?? "system"} · {timeAgo(a.created_at)}</span></li>))}</ul>
          )}
        </CardContent>
      </Card>
    </>
  );
}
