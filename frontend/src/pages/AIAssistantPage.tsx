import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Database, ListChecks, Sparkles } from "lucide-react";
import { useState } from "react";
import { ai } from "@/api/endpoints";
import { PageHeader } from "@/components/common/PageHeader";
import { QueryBoundary } from "@/components/common/States";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/useToast";
import { fmtDateTime, humanize } from "@/lib/utils";
import type { AIResult } from "@/types";

const QUICK = ["operations_summary", "bed_availability", "capacity_constraints", "low_stock", "pending_workflows", "alert_priorities", "bottlenecks"];

export default function AIAssistantPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AIResult | null>(null);
  const status = useQuery({ queryKey: ["ai", "status"], queryFn: ai.status });
  const execs = useQuery({ queryKey: ["ai", "executions"], queryFn: ai.executions });
  const run = useMutation({
    mutationFn: (v: { workflow: string; question?: string }) => ai.run(v.workflow, v.question ? { question: v.question } : {}),
    onSuccess: (r) => { setResult(r); qc.invalidateQueries({ queryKey: ["ai", "executions"] }); },
    onError: (e) => { toast.error((e as Error).message); qc.invalidateQueries({ queryKey: ["ai", "executions"] }); },
  });
  const titles = status.data?.workflows ?? {};

  return (
    <>
      <PageHeader title="AI Operations Assistant" description="Summaries and prioritisation from live hospital data. Read-only: it never changes records." />
      <div role="note" className="mb-4 rounded-md border bg-card p-3 text-sm">
        <Badge tone={status.data?.llm.configured ? "success" : "neutral"}>{status.data?.llm.configured ? `LLM: ${status.data.llm.provider}` : "Rule-based mode"}</Badge>{" "}
        {status.data?.llm.configured ? "An AI model adds a written narrative of the database facts." : "No AI provider is configured; analysis is deterministic and fully functional."}
        {" "}Not a clinical tool: it does not diagnose, prescribe, or make emergency decisions.
      </div>

      <Card className="mb-4"><CardContent className="space-y-3 p-4">
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (question.trim()) run.mutate({ workflow: "ask", question: question.trim() }); }}>
          <Input aria-label="Ask a question about current operations" placeholder="e.g. Which departments are near capacity? Which supplies are running low?" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={500} />
          <Button type="submit" disabled={run.isPending || !question.trim()}>Ask</Button>
        </form>
        <div className="flex flex-wrap gap-2">{QUICK.map((w) => <Button key={w} size="sm" variant="outline" disabled={run.isPending} onClick={() => run.mutate({ workflow: w })}>{titles[w] ?? humanize(w)}</Button>)}</div>
        {run.isPending && <p className="text-sm text-muted-foreground" aria-live="polite">Gathering facts…</p>}
      </CardContent></Card>

      {result && (
        <div className="mb-6 space-y-4">
          <Card><CardHeader><CardTitle className="flex items-center gap-2"><Bot className="h-4 w-4" />{result.title}<span className="text-xs font-normal text-muted-foreground">· {fmtDateTime(result.generated_at)} · engine: {result.engine}</span></CardTitle></CardHeader>
            <CardContent><p className="text-sm font-medium">{result.headline}</p></CardContent></Card>

          <Card><CardHeader><CardTitle className="flex items-center gap-2"><Database className="h-4 w-4" />Database facts <Badge tone="info">Retrieved from records</Badge></CardTitle></CardHeader>
            <CardContent><pre className="max-h-72 overflow-auto rounded-md bg-muted p-3 text-xs" tabIndex={0} aria-label="Raw facts">{JSON.stringify(result.facts, null, 2)}</pre></CardContent></Card>

          <Card><CardHeader><CardTitle className="flex items-center gap-2"><ListChecks className="h-4 w-4" />Rule-based recommendations <Badge tone="warning">For staff review</Badge></CardTitle></CardHeader>
            <CardContent>{result.recommendations.length === 0 ? <p className="text-sm text-muted-foreground">Nothing requires attention based on current data.</p> : (
              <ul className="space-y-2 text-sm">{result.recommendations.map((r, i) => (<li key={i} className="flex gap-2"><Badge tone={r.priority === "high" ? "danger" : r.priority === "medium" ? "warning" : "neutral"}>{r.priority}</Badge><span>{r.text}</span></li>))}</ul>)}</CardContent></Card>

          {result.ai_narrative && <Card><CardHeader><CardTitle className="flex items-center gap-2"><Sparkles className="h-4 w-4" />AI-generated narrative <Badge tone="warning">AI-generated, verify against facts</Badge></CardTitle></CardHeader><CardContent><p className="whitespace-pre-wrap text-sm">{result.ai_narrative}</p></CardContent></Card>}
          {result.warnings.map((w) => <p key={w} className="text-sm text-warning">{w}</p>)}
          <p className="text-xs text-muted-foreground">{result.disclaimer}</p>
        </div>
      )}

      <Card><CardHeader><CardTitle>Workflow execution history</CardTitle></CardHeader><CardContent>
        <QueryBoundary q={execs} empty={{ isEmpty: execs.data?.length === 0, title: "No workflows run yet" }}>
          <ul className="divide-y text-sm">{execs.data?.map((e) => (<li key={e.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <span><b>{humanize(e.workflow)}</b> <span className="text-muted-foreground">{e.output?.headline ?? e.error ?? ""}</span></span>
            <span className="flex items-center gap-2 text-xs text-muted-foreground"><StatusBadge status={e.status} />{e.used_llm ? "LLM" : "rule-based"} · {fmtDateTime(e.started_at)}</span></li>))}</ul>
        </QueryBoundary></CardContent></Card>
    </>
  );
}
