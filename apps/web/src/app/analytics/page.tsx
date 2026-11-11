import { useEffect, useState } from "react";
import { api } from "../../lib/api/client";

export default function AnalyticsPage() {
  const [a, setA] = useState<any>(null);
  useEffect(() => { api.analytics().then(setA); }, []);
  if (!a) return <div className="sub">Loading...</div>;
  const pct = (v: number | null) => (v == null ? "-" : `${Math.round(v * 100)}%`);
  return (
    <div>
      <div className="head"><div><h1>Analytics</h1><div className="sub">Your outcomes, cost and latency against the declared budgets, plus the latest evaluation results.</div></div></div>
      <div className="grid g4" style={{ marginBottom: 14 }} data-testid="analytics-stats">
        <div className="card"><div className="stat">{a.proposals_sent}<small>proposals sent</small></div></div>
        <div className="card"><div className="stat">{pct(a.reply_rate)}<small>reply rate</small></div></div>
        <div className="card"><div className="stat">{pct(a.win_rate)}<small>win rate</small></div></div>
        <div className="card"><div className="stat">{a.connects_per_hire ?? "-"}<small>Connects per hire ({a.connects_spent} spent)</small></div></div>
      </div>
      <div className="grid g2">
        <div className="card"><h2>Runs: cost and latency</h2>
          <table><thead><tr><th>kind</th><th>status</th><th>n</th><th>avg USD</th><th>p95 s</th><th>tokens</th></tr></thead>
            <tbody>{a.runs.map((r: any, i: number) => <tr key={i}><td>{r.kind}</td><td>{r.status}</td><td>{r.n}</td><td>{Number(r.cost || 0).toFixed(5)}</td><td>{Number(r.p95 || 0).toFixed(1)}</td><td>{r.tok}</td></tr>)}</tbody></table>
          <h3 style={{ marginTop: 12 }}>Declared budgets</h3>
          <dl className="kv">{Object.entries(a.declared_budgets || {}).map(([k, v]) => <><dt key={k}>{k}</dt><dd>{String(v)}</dd></>)}</dl>
        </div>
        <div className="card"><h2>Evaluation results (from evals/results)</h2>
          <pre className="mono pre" style={{ maxHeight: 420, overflow: "auto" }}>{JSON.stringify(a.evals, null, 1)}</pre></div>
      </div>
    </div>
  );
}
