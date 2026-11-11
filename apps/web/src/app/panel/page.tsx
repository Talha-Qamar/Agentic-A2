import { useEffect, useState } from "react";

/** Blind pairwise panel: two anonymised proposals for the same job, sides randomised. No login. */
export default function PanelPage() {
  const [rater, setRater] = useState(() => { try { return localStorage.getItem("gb_rater") || ""; } catch { return ""; } });
  const [pair, setPair] = useState<any>(null);
  const load = async (r = rater) => { const x = await fetch(`/api/panel/pair?rater=${encodeURIComponent(r)}`).then((x) => x.json()); setPair(x); };
  useEffect(() => { if (rater) load(); }, []);
  const vote = async (choice: string) => {
    await fetch("/api/panel/vote", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pair_id: pair.pair_id, rater, choice, flip: pair.flip }) });
    load();
  };
  return (
    <div className="main" style={{ margin: "0 auto" }}>
      <h1>GigBid proposal panel</h1>
      <p className="sub">You are a client. For each job, pick the proposal you would rather reply to. The two proposals were written by different systems; you do not know which. Takes about 10 minutes.</p>
      {!pair && (
        <div className="card auth"><label>Your name or roll number (only used to avoid duplicate votes)</label>
          <input value={rater} onChange={(e) => setRater(e.target.value)} />
          <button className="btn primary" style={{ marginTop: 10 }} disabled={rater.length < 2} onClick={() => { try { localStorage.setItem("gb_rater", rater); } catch { /* ok */ } load(rater); }}>Start</button></div>
      )}
      {pair?.done && <div className="card">Thank you - you have rated all {pair.total} pairs.</div>}
      {pair && !pair.done && (
        <div>
          <div className="card" style={{ marginBottom: 12 }}><h3>Job ({pair.total - pair.remaining + 1} of {pair.total})</h3><div className="pre sub" style={{ maxHeight: 180, overflow: "auto" }}>{pair.job}</div></div>
          <div className="grid g2">
            {["A", "B"].map((k) => (
              <div className="card" key={k}><h2>Proposal {k}</h2><div className="pre">{pair[k]}</div>
                <button className="btn primary" style={{ marginTop: 10 }} onClick={() => vote(k)}>I prefer {k}</button></div>
            ))}
          </div>
          <button className="btn" style={{ marginTop: 10 }} onClick={() => vote("tie")}>No preference</button>
        </div>
      )}
    </div>
  );
}
