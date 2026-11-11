import { useEffect, useRef, useState } from "react";

export const Badge = ({ v, testid }: { v?: string | null; testid?: string }) =>
  v ? <span className={`badge ${v}`} data-testid={testid}>{v.replace(/_/g, " ")}</span> : <span className="sub">-</span>;

export const Score = ({ v }: { v?: number | null }) =>
  v == null ? <span className="sub">-</span> : <span><span className="bar"><span style={{ width: `${Math.round(v * 100)}%` }} /></span>{v.toFixed(2)}</span>;

export const money = (v?: number | null) => (v == null ? "-" : `$${Math.round(v).toLocaleString()}`);

const STEPS = ["intake", "analyst", "risk", "matcher", "decide", "pricing", "writer", "verifier", "critic", "compliance", "preview", "approval", "submit"];

/** Live node-by-node progress for a graph thread (Server-Sent Events from /api/runs/:id/stream). */
export function RunStream({ threadId, onEnd }: { threadId: string; onEnd?: () => void }) {
  const [events, setEvents] = useState<any[]>([]);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!threadId) return;
    setEvents([]);
    const es = new EventSource(`/api/runs/${encodeURIComponent(threadId)}/stream`, { withCredentials: true });
    const add = (kind: string) => (e: MessageEvent) => {
      const d = JSON.parse(e.data);
      setEvents((x) => [...x, { kind, ...d }]);
      if (kind === "run_end") onEnd?.();
    };
    ["node_start", "node_end", "tool_call", "tool_result", "node_error", "node_retry", "dead_letter", "budget_exceeded", "needs_attention", "run_end", "memory_error"]
      .forEach((k) => es.addEventListener(k, add(k) as any));
    return () => es.close();
  }, [threadId]);
  useEffect(() => { ref.current?.scrollTo(0, 1e9); }, [events.length]);
  const done = new Set(events.filter((e) => e.kind === "node_end").map((e) => e.node));
  const failed = new Set(events.filter((e) => e.kind === "node_error").map((e) => e.node));
  const started = events.filter((e) => e.kind === "node_start").map((e) => e.node);
  const now = started.find((n) => !done.has(n) && !failed.has(n));
  return (
    <div data-testid="run-stream">
      <div className="flow" style={{ marginBottom: 8 }}>
        {STEPS.map((s) => <span key={s} className={failed.has(s) ? "fail" : done.has(s) ? "done" : now === s ? "now" : ""}>{s}</span>)}
      </div>
      <div className="events" ref={ref}>
        {events.length === 0 && <div className="sub">Waiting for events...</div>}
        {events.map((e, i) => (
          <div key={i} className={`ev ${e.kind}`}>
            <b>{e.node}</b> {e.kind}
            {e.payload?.tool ? ` ${e.payload.tool}` : ""}
            {e.payload?.ms != null ? ` - ${e.payload.ms} ms` : ""}
            {e.payload?.tokens ? ` - ${e.payload.tokens} tok` : ""}
            {e.payload?.cost_usd ? ` - $${Number(e.payload.cost_usd).toFixed(5)}` : ""}
            {e.payload?.error ? ` - ${e.payload.error}` : ""}
            {e.kind === "run_end" ? ` - ${e.payload?.status}` : ""}
          </div>
        ))}
      </div>
    </div>
  );
}
