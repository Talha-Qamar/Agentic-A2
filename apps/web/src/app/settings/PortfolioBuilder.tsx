import { useEffect, useState } from "react";
import { api } from "../../lib/api/client";

/** Extension X3: what to write next, and repo -> verified case study through the GitHub MCP server. */
const DEMO_REPO: Record<string, string> = { ai_ml_engineer: "clause-rag", fullstack_web_dev: "clinic-api", data_analyst: "ab-toolkit" };

export default function PortfolioBuilder({ persona }: { persona?: string }) {
  const [sug, setSug] = useState<any>(null);
  const [f, setF] = useState({ owner: "Talha-Qamar", repo: "Agentic-A2", path: `data/personas/${persona || "ai_ml_engineer"}/repos/${DEMO_REPO[persona || "ai_ml_engineer"] || "clause-rag"}` });
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.portfolioSuggestions().then(setSug).catch(() => setSug({ suggestions: [] })); }, []);
  const run = async () => {
    setBusy(true); setErr(""); setRes(null);
    try { setRes(await api.fromGithub(f)); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="card" style={{ marginTop: 14 }} data-testid="portfolio-builder">
      <h2>Portfolio builder</h2>
      <p className="sub">Case studies GigBid thinks you should write next, ranked by the jobs you had to skip for lack of evidence
        ({sug?.jobs_considered ?? 0} analysed jobs) and by skills your code shows but your write-ups never mention.</p>
      {(sug?.suggestions || []).map((x: any) => (
        <div key={x.skill} className="claim" data-testid="builder-suggestion"><b>{x.skill}</b> <span className="sub">{x.jobs_affected} jobs, ${x.budget_at_stake} at stake</span><div>{x.action}</div></div>))}
      <h3 style={{ marginTop: 12 }}>Build a case study from a GitHub repo</h3>
      <div className="row">
        <input value={f.owner} onChange={(e) => setF({ ...f, owner: e.target.value })} placeholder="owner" style={{ maxWidth: 140 }} />
        <input value={f.repo} onChange={(e) => setF({ ...f, repo: e.target.value })} placeholder="repo" style={{ maxWidth: 140 }} />
        <input value={f.path} onChange={(e) => setF({ ...f, path: e.target.value })} placeholder="path (optional)" />
        <button className="btn primary" disabled={busy} onClick={run} data-testid="build-case-study">{busy ? "Building..." : "Build and verify"}</button>
      </div>
      {err && <div className="banner">{err}</div>}
      {res && (
        <div data-testid="builder-result" style={{ marginTop: 10 }}>
          <div className="sub">Read {res.files_read} files via {res.source}. Saved to <span className="mono">{res.saved}</span>.
            Claims checked against the code: {res.verification.claims}, removed as unsupported: {res.verification.unsupported}.</div>
          {res.checks.map((c: any, i: number) => <div key={i} className={`claim ${c.verdict}`}><span className={`badge ${c.verdict}`}>{c.verdict}</span> {c.text} <span className="sub">{c.note}</span></div>)}
          <div className="pre" style={{ marginTop: 8 }}>{res.markdown}</div>
        </div>)}
    </div>
  );
}
