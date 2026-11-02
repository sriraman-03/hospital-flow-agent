import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Page } from "@/types";

export function Pagination({ data, onPage }: { data?: Pick<Page<unknown>, "page" | "pages" | "total">; onPage: (p: number) => void }) {
  if (!data || data.total === 0) return null;
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-2 border-t px-3 py-2 text-sm">
      <span className="text-muted-foreground">{data.total} result{data.total === 1 ? "" : "s"} · page {data.page} of {data.pages}</span>
      <div className="flex gap-1">
        <Button variant="outline" size="sm" disabled={data.page <= 1} onClick={() => onPage(data.page - 1)}><ChevronLeft className="h-4 w-4" />Prev</Button>
        <Button variant="outline" size="sm" disabled={data.page >= data.pages} onClick={() => onPage(data.page + 1)}>Next<ChevronRight className="h-4 w-4" /></Button>
      </div>
    </nav>
  );
}
