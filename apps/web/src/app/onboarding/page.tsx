import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../App";
import { api } from "../../lib/api/client";

export default function OnboardingPage() {
  const [personas, setPersonas] = useState<any[]>([]);
  const [sel, setSel] = useState("ai_ml_engineer");
  const [busy, setBusy] = useState(false);
  const { refresh } = useAuth();
  const nav = useNavigate();
  useEffect(() => { api.personas().then(setPersonas); }, []);
  const go = async () => { setBusy(true); await api.onboard(sel); await refresh(); nav("/inbox"); };
  const upload = async (f: FileList | null) => { if (!f?.length) return; setBusy(true); await api.upload(f); await api.onboard(sel); await refresh(); nav("/inbox"); };
  return (
    <div className="main" style={{ margin: "0 auto" }}>
      <h1>Set up your profile</h1>
      <p className="sub">Pick a demo persona (synthetic data, clearly labelled) or upload your own portfolio files - CV (PDF), case studies (Markdown), reviews.json, past_proposals.jsonl.</p>
      <div className="grid g3" style={{ margin: "16px 0" }}>
        {personas.map((p) => (
          <div key={p.id} className={`card persona ${sel === p.id ? "sel" : ""}`} onClick={() => setSel(p.id)} data-testid={`persona-${p.id}`}>
            <h2>{p.name} <span className="badge info">synthetic</span></h2>
            <div style={{ fontWeight: 600 }}>{p.headline}</div>
            <p className="sub">{p.summary}</p>
          </div>
        ))}
      </div>
      <div className="row">
        <button className="btn primary" disabled={busy} onClick={go} data-testid="onboard-continue">Use this persona</button>
        <label className="btn" style={{ margin: 0, width: "auto" }}>Upload my own files
          <input type="file" multiple style={{ display: "none" }} onChange={(e) => upload(e.target.files)} />
        </label>
      </div>
    </div>
  );
}
