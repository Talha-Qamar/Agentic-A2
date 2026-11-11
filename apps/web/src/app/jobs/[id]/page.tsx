import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Badge, money, RunStream, Score } from "../../../components/ui";
import { api } from "../../../lib/api/client";

export default function JobPage() {
  const { id = "" } = useParams();
  const [d, setD] = useState<any>(null);
  const load = () => api.job(id).then(setD).catch(() => setD({ missing: true }));
  useEffect(() => { load(); const t = setInterval(load, 6000); return () => clearInterval(t); }, [id]);
  if (!d) return <div className="sub">Loading...</div>;
  if (d.missing) return <div className="empty">Job not found. <button className="btn" onClick={() => api.addJob(id).then(load)}>Analyse {id}</button></div>;
  const s = d.summary || {};
  const fit = s.fit || {}, risk = s.risk || {}, dec = s.decision || {}, price = s.price || {}, spec = s.job_spec || {};
  return (
    <div>
      <div className="head">
        <div><h1>{spec.summary || d.title}</h1><div className="sub mono">{id} {d.duplicate_of && `- repost of ${d.duplicate_of}`}</div></div>
        <div className="row">
          <Badge v={dec.action || d.status} testid="job-decision" />
          {d.thread_id && <Link className="btn" to={`/runs/${d.thread_id}`}>Run trace</Link>}
          {s.pending_approval && <Link className="btn primary" to={`/studio/${d.thread_id}`} data-testid="open-studio">Open proposal studio</Link>}
          <button className="btn" onClick={() => api.analyse(id, true).then(load)}>Re-analyse</button>
        </div>
      </div>
      <div className="grid g3" style={{ marginBottom: 14 }}>
        <div className="card"><h3>Fit</h3><div className="stat"><Score v={fit.fit_score} /><small>coverage {fit.coverage ?? "-"} - retrieval {fit.variant}</small></div></div>
        <div className="card"><h3>Risk</h3><div className="stat"><Score v={risk.risk_score} /><small>scam {risk.scam_score ?? "-"} - client quality {risk.client_quality ?? "-"}</small></div></div>
        <div className="card"><h3>Price</h3><div className="stat">{money(price.amount)}{price.bid_type === "hourly" ? "/h" : ""}<small>{price.connects_cost != null ? `${price.connects_cost} Connects ($${price.connects_usd}) - EV $${price.expected_value_usd}` : ""}</small></div></div>
      </div>
      <div className="grid g2">
        <div className="card">
          <h2>Why: {dec.action || "pending"}</h2>
          <ul>{(dec.reasons || [s.status_reason]).filter(Boolean).map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>
          <div className="sub mono">{(dec.rule_trace || []).join(" | ")}</div>
          {price.rationale && <p className="sub">{price.rationale}</p>}
          <h3 style={{ marginTop: 12 }}>Requirements vs evidence</h3>
          <table><tbody>{(fit.matches || []).map((m: any) => (
            <tr key={m.requirement_id}><td>{m.requirement}</td><td><Badge v={m.support === "strong" ? "supported" : m.support === "partial" ? "partial" : "unsupported"} /></td><td className="mono">{m.score}</td></tr>
          ))}</tbody></table>
        </div>
        <div className="card">
          <h2>Risk flags</h2>
          {(risk.flags || []).length === 0 && <div className="sub">No flags.</div>}
          {(risk.flags || []).map((f: any, i: number) => <div key={i} className="claim"><Badge v={f.severity === "high" ? "avoid" : "caution"} /> <b>{f.type}</b>: {f.evidence}</div>)}
          {risk.injection_detected && <div className="claim"><Badge v="blocked" /> Prompt injection detected and quarantined: <span className="mono">{(risk.quarantined_spans || []).join(" | ").slice(0, 200)}</span></div>}
          <h3 style={{ marginTop: 12 }}>Job post (untrusted)</h3>
          <div className="pre sub" style={{ maxHeight: 260, overflow: "auto" }}>{d.data?.snippet || ""}</div>
        </div>
      </div>
      {d.thread_id && <div className="card" style={{ marginTop: 14 }}><h2>Live run</h2><RunStream threadId={d.thread_id} onEnd={load} /></div>}
    </div>
  );
}
