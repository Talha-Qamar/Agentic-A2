import { useEffect, useState } from "react";

/** Judge calibration: the student scores 30 proposals 1-10; agreement with the LLM judge is computed offline. */
export default function LabelPage() {
  const [who, setWho] = useState("");
  const [item, setItem] = useState<any>(null);
  const [score, setScore] = useState(6);
  const load = async () => setItem(await fetch(`/api/panel/label?labeller=${encodeURIComponent(who)}`).then((x) => x.json()));
  useEffect(() => { if (who) load(); }, [who]);
  const save = async () => {
    await fetch("/api/panel/label", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ item_id: item.item_id, labeller: who, score }) });
    setScore(6); load();
  };
  return (
    <div className="main" style={{ margin: "0 auto" }}>
      <h1>Judge calibration labels</h1>
      <p className="sub">Score each proposal 1-10 the way a client would: specific to the job, credible evidence, clear, answers the requirements, right length. Do not look at the LLM judge's scores.</p>
      {!who && <div className="card auth"><label>Labeller</label><input onKeyDown={(e) => { if (e.key === "Enter") setWho((e.target as HTMLInputElement).value); }} placeholder="type your name, press Enter" /></div>}
      {item?.done && <div className="card">All {item.total} items labelled. Thank you.</div>}
      {item && !item.done && (
        <div className="grid g2">
          <div className="card"><h3>Job</h3><div className="pre sub" style={{ maxHeight: 420, overflow: "auto" }}>{item.job}</div></div>
          <div className="card"><h3>Proposal ({item.total - item.remaining + 1} of {item.total})</h3><div className="pre">{item.proposal}</div>
            <label>Score: {score}</label><input type="range" min={1} max={10} value={score} onChange={(e) => setScore(Number(e.target.value))} />
            <button className="btn primary" style={{ marginTop: 10 }} onClick={save}>Save and next</button></div>
        </div>
      )}
    </div>
  );
}
