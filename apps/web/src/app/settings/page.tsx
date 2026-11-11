import { useEffect, useState } from "react";
import { api } from "../../lib/api/client";
import PortfolioBuilder from "./PortfolioBuilder";

export default function SettingsPage() {
  const [s, setS] = useState<any>(null);
  const [mem, setMem] = useState<any>(null);
  const [searches, setSearches] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [saved, setSaved] = useState("");
  const load = () => { api.settings().then(setS); api.memory().then(setMem); api.searches().then(setSearches); };
  useEffect(load, []);
  if (!s) return <div className="sub">Loading...</div>;
  const set = (k: string, v: any) => setS({ ...s, settings: { ...s.settings, [k]: v } });
  const save = async () => {
    await api.saveSettings({ hourly_floor: Number(s.settings.hourly_floor), target_rate: Number(s.settings.target_rate), autonomy: s.settings.autonomy,
      timezone: s.settings.timezone, working_hours: s.settings.working_hours } as any);
    setSaved("Saved.");
  };
  return (
    <div>
      <div className="head"><div><h1>Settings</h1><div className="sub">Rates, autonomy, saved searches, connections and what GigBid has learned about you.</div></div></div>
      <div className="grid g2">
        <div className="card">
          <h2>Rates and autonomy</h2>
          <label>Hourly floor (USD) - GigBid never prices or negotiates below this</label>
          <input type="number" value={s.settings.hourly_floor} onChange={(e) => set("hourly_floor", e.target.value)} data-testid="floor" />
          <label>Target hourly rate (USD)</label><input type="number" value={s.settings.target_rate} onChange={(e) => set("target_rate", e.target.value)} />
          <label>Time zone</label><input value={s.settings.timezone} onChange={(e) => set("timezone", e.target.value)} />
          <label>Autonomy</label>
          <select value={s.settings.autonomy} onChange={(e) => set("autonomy", e.target.value)} data-testid="autonomy">
            <option value="suggest">Suggest only (default)</option>
            <option value="auto_skip">Auto-skip clearly low-fit jobs</option>
          </select>
          <p className="sub">Sending proposals, messages and spending Connects always needs your approval - there is no auto-send level.</p>
          <div className="row"><button className="btn primary" onClick={save} data-testid="save-settings">Save</button><span className="sub">{saved}</span></div>
          <h2 style={{ marginTop: 18 }}>Marketplace</h2>
          <p>Mode: <b>{s.marketplace_mode}</b> {s.upwork_connected ? "(Upwork connected)" : ""}</p>
          <button className="btn" onClick={async () => { try { const r = await api.upworkStart(); window.open(r.authorize_url, "_blank"); } catch (e: any) { alert(e.message); } }}>Connect Upwork account (OAuth)</button>
        </div>
        <div className="card">
          <h2>Saved searches</h2>
          {searches.map((x) => <div key={x.search_id} className="row" style={{ justifyContent: "space-between" }}><span>{x.query} <span className="sub">every {x.interval_minutes} min</span></span>
            <button className="btn" onClick={() => api.delSearch(x.search_id).then(load)}>Remove</button></div>)}
          <div className="row" style={{ marginTop: 8 }}><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="keywords" /><button className="btn" onClick={() => q && api.addSearch(q).then(() => { setQ(""); load(); })}>Add</button></div>
          <h2 style={{ marginTop: 18 }}>Memory</h2>
          <p className="sub">Promotion rule: an edit pattern becomes a style rule only after it appears in {mem?.rules?.style?.min_occurrences} separate edits within your last {mem?.rules?.style?.window_edits}; outcome stats need {mem?.rules?.outcome?.min_samples} resolved proposals in a category.</p>
          <h3>Style rules</h3>
          {(mem?.style || []).length === 0 && <div className="sub">None learned yet.</div>}
          {(mem?.style || []).map((m: any) => <div key={m.key} className="claim row" style={{ justifyContent: "space-between" }} data-testid="memory-item"><span>{m.rule} <span className="sub">({m.occurrences} edits)</span></span><button className="btn" onClick={() => api.forget("style", m.key).then(load)}>Forget</button></div>)}
          <h3>Outcome insights</h3>
          {(mem?.outcomes || []).map((m: any) => <div key={m.key} className="claim row" style={{ justifyContent: "space-between" }}><span>{m.text}</span><button className="btn" onClick={() => api.forget("outcomes", m.key).then(load)}>Forget</button></div>)}
          <h3>Candidates (not yet promoted)</h3>
          {(mem?.candidates || []).filter((c: any) => !c.promoted).map((c: any) => <div key={c.key} className="sub">{c.kind}: {c.key} x{c.occurrences}</div>)}
        </div>
      </div>
      <PortfolioBuilder persona={s.persona} />
    </div>
  );
}
