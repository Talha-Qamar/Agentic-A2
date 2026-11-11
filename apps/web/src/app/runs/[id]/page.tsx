import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Badge } from "../../../components/ui";
import { api } from "../../../lib/api/client";

/** Run viewer: every node, tool call, argument summary, tokens and cost for one thread (also the public trace page). */
export default function RunPage({ publicView = false }: { publicView?: boolean }) {
  const { id = "" } = useParams();
  const [r, setR] = useState<any>(null);
  useEffect(() => { (publicView ? api.publicTrace(id) : api.run(id)).then(setR).catch(() => setR({ missing: true })); }, [id, publicView]);
  const toggle = async () => { const x = await api.setPublic(id, !r.run.public); setR({ ...r, run: { ...r.run, public: x.public } }); };
  if (!r) return <div className="sub">Loading...</div>;
  if (r.missing) return <div className="empty">Run not found.</div>;
  const trace = r.summary?.trace || [];
  return (
    <div>
      <div className="head"><div><h1>Run trace</h1><div className="sub mono">{id} - trace {r.run.trace_id}</div></div>
        <div className="row"><Badge v={r.run.status} />
          {!publicView && <button className="btn" data-testid="toggle-public" onClick={toggle}>{r.run.public ? "Unpublish trace" : "Make trace public"}</button>}
          {!publicView && r.run.public && <a className="btn" href={`/t/${id}`} target="_blank">Public link</a>}
          {r.phoenix_url && <a className="btn" href={r.phoenix_url} target="_blank">Open in Phoenix</a>}</div></div>
      <div className="grid g4" style={{ marginBottom: 14 }}>
        <div className="card"><div className="stat">{r.run.tokens}<small>tokens</small></div></div>
        <div className="card"><div className="stat">${Number(r.run.cost_usd || 0).toFixed(5)}<small>cost (list price)</small></div></div>
        <div className="card"><div className="stat">{Number(r.run.latency_s || 0).toFixed(1)}s<small>wall time</small></div></div>
        <div className="card"><div className="stat">{r.events.length}<small>events</small></div></div>
      </div>
      <div className="grid g2">
        <div className="card"><h2>Per node</h2>
          <table data-testid="trace-table"><thead><tr><th>node</th><th>ms</th><th>tokens</th><th>USD</th><th>models</th></tr></thead>
            <tbody>{trace.map((t: any, i: number) => (
              <tr key={i}><td>{t.node}{t.degraded ? " (fallback)" : ""}{t.error ? " !" : ""}</td><td>{t.ms}</td><td>{t.tokens}</td><td>{Number(t.cost_usd || 0).toFixed(5)}</td>
                <td className="mono">{Array.from(new Set((t.llm_calls || []).map((c: any) => c.model))).join(", ")}</td></tr>))}</tbody></table>
        </div>
        {(r.audit || []).length > 0 && <div className="card"><h2>MCP audit log (same trace id)</h2>
          <table><thead><tr><th>time</th><th>server</th><th>tool</th><th>status</th></tr></thead>
            <tbody>{r.audit.map((a: any, i: number) => (<tr key={i}><td>{new Date(a.ts).toLocaleTimeString()}</td><td>{a.server}</td><td className="mono">{a.tool}</td><td>{a.status}</td></tr>))}</tbody></table>
        </div>}
        <div className="card"><h2>Event log</h2>
          <div className="events">{r.events.map((e: any) => (
            <div key={e.id} className={`ev ${e.kind}`}><b>{e.node}</b> {e.kind} <span className="sub">{new Date(e.ts).toLocaleTimeString()}</span>
              <div className="pre">{JSON.stringify(e.payload).slice(0, 400)}</div></div>))}</div>
        </div>
      </div>
    </div>
  );
}
