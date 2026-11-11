import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, money, Score } from "../../components/ui";
import { api, JobRow } from "../../lib/api/client";

export default function InboxPage() {
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [approvals, setApprovals] = useState<any[]>([]);
  const [filter, setFilter] = useState("all");
  const [jobId, setJobId] = useState("");
  const [msg, setMsg] = useState("");
  const load = () => { api.jobs().then(setJobs); api.approvals().then(setApprovals); };
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, []);
  const shown = jobs.filter((j) => filter === "all" ? !j.duplicate_of : filter === "duplicates" ? !!j.duplicate_of : j.action === filter);
  return (
    <div>
      <div className="head">
        <div><h1>Job inbox</h1><div className="sub">Every job the scout found, with fit, risk, suggested price and the reason for the decision.</div></div>
        <div className="row">
          <button className="btn" onClick={async () => { await api.advance(180); setMsg("Advanced the marketplace clock by 3 hours."); }} data-testid="advance">Advance time</button>
          <button className="btn primary" onClick={async () => { await api.scout(); setMsg("Scout queued - new jobs appear here as they are analysed."); }} data-testid="scout-now">Scout now</button>
        </div>
      </div>
      {msg && <div className="card sub" style={{ marginBottom: 12 }}>{msg}</div>}
      {approvals.length > 0 && (
        <div className="card" style={{ marginBottom: 14, borderColor: "var(--warn)" }} data-testid="approvals-panel">
          <h2>Waiting for your approval ({approvals.length})</h2>
          {approvals.map((a) => (
            <div key={a.approval_id} className="row" style={{ justifyContent: "space-between", borderTop: "1px solid var(--line)", padding: "8px 0" }}>
              <span>{a.kind === "proposal_approval" ? `Proposal: ${a.payload.job_title}` : `Reply in thread ${a.payload.marketplace_thread_id}`}
                {a.payload.connects_cost != null && <span className="sub"> - {a.payload.connects_cost} Connects</span>}</span>
              <Link className="btn primary" to={a.kind === "proposal_approval" ? `/studio/${a.thread_id}` : "/messages"} data-testid="open-approval">Review</Link>
            </div>
          ))}
        </div>
      )}
      <div className="row" style={{ marginBottom: 10 }}>
        {["all", "bid", "watch", "skip", "duplicates"].map((f) => (
          <button key={f} className={`btn ${filter === f ? "primary" : ""}`} onClick={() => setFilter(f)}>{f}</button>
        ))}
        <span style={{ flex: 1 }} />
        <input placeholder="Analyse a job id..." value={jobId} onChange={(e) => setJobId(e.target.value)} style={{ width: 220 }} data-testid="job-id-input" />
        <button className="btn" onClick={async () => { if (jobId) { await api.addJob(jobId.trim()); setJobId(""); load(); } }} data-testid="analyse-job">Analyse</button>
      </div>
      <div className="card" style={{ padding: 0 }}>
        <table data-testid="inbox-table">
          <thead><tr><th>Job</th><th>Decision</th><th>Fit</th><th>Risk</th><th>Price</th><th>Connects</th><th>Why</th></tr></thead>
          <tbody>
            {shown.map((j) => (
              <tr key={j.job_id} data-testid="inbox-row">
                <td><Link to={`/jobs/${encodeURIComponent(j.job_id)}`}>{j.title || j.job_id}</Link><div className="sub mono">{j.job_id}{j.duplicate_of ? ` - repost of ${j.duplicate_of}` : ""}</div></td>
                <td>{j.action ? <Badge v={j.action} /> : <Badge v={j.status} />}</td>
                <td><Score v={j.fit_score} /></td>
                <td><Score v={j.risk_score} /></td>
                <td>{money(j.price)}</td>
                <td>{j.connects_cost ?? "-"}</td>
                <td className="sub" style={{ maxWidth: 320 }}>{j.reason || ""}</td>
              </tr>
            ))}
            {shown.length === 0 && <tr><td colSpan={7} className="empty">No jobs yet. Click "Scout now" (and "Advance time" to let the simulated marketplace post new jobs).</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
