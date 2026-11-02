import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/hooks/useToast";

/** Mutation with consistent error toasts, success message and cache invalidation. */
export function useApiMutation<V, R>(fn: (v: V) => Promise<R>, opts: { success?: string | ((r: R) => string); invalidate?: string[]; onSuccess?: (r: R) => void } = {}) {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: fn,
    onSuccess: (r) => {
      if (opts.success) toast.success(typeof opts.success === "function" ? opts.success(r) : opts.success);
      // Operational data is interlinked (beds <-> patients <-> dashboard), so invalidate broadly.
      (opts.invalidate ?? ["patients", "beds", "resources", "departments", "transfers", "discharges", "notifications", "unread", "dashboard", "audit"]).forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      opts.onSuccess?.(r);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Request failed"),
  });
}
