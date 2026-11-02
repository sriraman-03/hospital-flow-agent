import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { admin } from "@/api/endpoints";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { QueryBoundary } from "@/components/common/States";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useDebounce } from "@/hooks/useDebounce";
import { fmtDateTime } from "@/lib/utils";

const ENTITIES = ["patient", "bed", "resource", "transfer", "discharge", "notification", "user", "department", "settings", "ai_workflow"];

export default function AuditLogsPage() {
  const [action, setAction] = useState(""), [entity, setEntity] = useState(""), [page, setPage] = useState(1);
  const da = useDebounce(action);
  const list = useQuery({ queryKey: ["audit", da, entity, page], queryFn: () => admin.audit({ action: da, entity_type: entity, page, page_size: 25 }), placeholderData: (p) => p });
  return (
    <>
      <PageHeader title="Audit Logs" description="Who did what, and when. Passwords, tokens and patient identifiers are never recorded here." />
      <Card>
        <div className="flex flex-wrap gap-2 border-b p-3">
          <Input className="w-60" placeholder="Filter by action (e.g. bed.assigned)" aria-label="Filter by action" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} />
          <Select className="w-48" aria-label="Filter by entity type" value={entity} onChange={(e) => { setEntity(e.target.value); setPage(1); }}><option value="">All entities</option>{ENTITIES.map((x) => <option key={x} value={x}>{x}</option>)}</Select>
        </div>
        <QueryBoundary q={list} empty={{ isEmpty: list.data?.total === 0, title: "No audit records match" }}>
          <Table><THead><TR><TH>Time</TH><TH>Actor</TH><TH>Action</TH><TH>Entity</TH><TH>Details</TH></TR></THead>
            <TBody>{list.data?.items.map((a) => (<TR key={a.id}><TD className="whitespace-nowrap">{fmtDateTime(a.created_at)}</TD><TD>{a.actor_email ?? "system"}</TD><TD className="font-mono text-xs">{a.action}</TD><TD>{a.entity_type}{a.entity_id ? ` #${a.entity_id}` : ""}</TD>
              <TD className="max-w-md truncate font-mono text-xs" title={a.details ? JSON.stringify(a.details) : ""}>{a.details ? JSON.stringify(a.details) : "—"}</TD></TR>))}</TBody></Table>
          <Pagination data={list.data} onPage={setPage} />
        </QueryBoundary>
      </Card>
    </>
  );
}
