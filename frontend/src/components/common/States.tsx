import { AlertTriangle, Inbox } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-center">
      <Inbox className="h-8 w-8 text-muted-foreground" aria-hidden />
      <p className="font-medium">{title}</p>
      {hint && <p className="max-w-sm text-sm text-muted-foreground">{hint}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-2 py-12 text-center">
      <AlertTriangle className="h-8 w-8 text-destructive" aria-hidden />
      <p className="font-medium">Something went wrong</p>
      <p className="max-w-md text-sm text-muted-foreground">{error instanceof Error ? error.message : "Unknown error"}</p>
      {onRetry && <Button variant="outline" size="sm" onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
    </div>
  );
}

/** Standard loading / error / empty handling around a query. */
export function QueryBoundary({ q, empty, children, skeleton }: {
  q: { isLoading: boolean; isError: boolean; error: unknown; refetch: () => unknown };
  empty?: { isEmpty: boolean; title: string; hint?: string; action?: ReactNode };
  skeleton?: ReactNode; children: ReactNode;
}) {
  if (q.isLoading) return <>{skeleton ?? <TableSkeleton />}</>;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (empty?.isEmpty) return <EmptyState title={empty.title} hint={empty.hint} action={empty.action} />;
  return <>{children}</>;
}
