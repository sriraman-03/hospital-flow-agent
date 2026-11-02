import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { WS_ROOT, tokenStore } from "@/api/client";

/** WebSocket change signals -> refetch via the REST API. Polling (refetchInterval on the queries) is the fallback. */
export function useLiveNotifications(enabled: boolean) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!enabled) return;
    let ws: WebSocket | null = null, retry: number | undefined, ping: number | undefined, closed = false, attempts = 0;
    const refresh = () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["unread"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    };
    const connect = () => {
      const token = tokenStore.get();
      if (!token || closed) return;
      ws = new WebSocket(`${WS_ROOT}/ws/notifications?token=${encodeURIComponent(token)}`);
      ws.onopen = () => { attempts = 0; ping = window.setInterval(() => ws?.readyState === 1 && ws.send("ping"), 25000); };
      ws.onmessage = refresh;
      ws.onclose = () => { window.clearInterval(ping); if (!closed) retry = window.setTimeout(connect, Math.min(30000, 1000 * 2 ** attempts++)); };
    };
    connect();
    return () => { closed = true; window.clearTimeout(retry); window.clearInterval(ping); ws?.close(); };
  }, [enabled, qc]);
}
