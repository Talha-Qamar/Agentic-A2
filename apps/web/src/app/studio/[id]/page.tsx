import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Badge, money, RunStream } from "../../../components/ui";
import { api } from "../../../lib/api/client";

/** Proposal Studio: draft with claim-level evidence, critique, compliance verdict, exact dry-run preview and the
 * human approval controls (approve / edit / regenerate one paragraph / reject). */
export default function StudioPage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [run, setRun] = useState<any>(null);
  const [appr, setAppr] = useState<any>(null);
  const [text, setText] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState("");
  const load = async () => {
    const r = await api.run(id); setRun(r);
    const a = (await api.approvals()).find((x: any) => x.thread_id === id) || null;
    setAppr(a);
    if (a && !busy) setText(a.payload.cover_letter);
  };
  useEffect(() => { load(); }, [id]);
  const s = run?.summary || {};
  const draft = s.draft || {};
  const evidence: Record<string, any> = Object.fromEntries((s.evidence || []).map((e: any) => [e.evidence_id, e]));
  const decide = async (action: string, extra: any = {}) => {
    if (!appr) return;
    setBusy(true);
    await api.decide(appr.approval_id, { action, ...extra } as any);
    setDone(action === "approve" ? "Approved - submitting with the exact preview shown." : action === "reject" ? "Rejected." : "Sent back to the agents - a new draft will appear for approval.");
    setTimeout(() => { setBusy(false); load(); }, 1500);
  };
  const paras = (appr?.payload.cover_letter || "").split(/\n\s*\n/);
  return (
    <div>
      <div className="head">
        <div><h1>Proposal studio</h1><div className="sub">{appr?.payload.job_title || s.job_spec?.summary} - thread <span className="mono">{id}</span></div></div>
        <div className="row"><Badge v={run?.run?.status} testid="studio-status" /><Link className="btn" to={`/runs/${id}`}>Trace</Link></div>
      </div>
      {done && <div className="card" style={{ marginBottom: 12 }} data-testid="studio-done">{done}</div>}
      {!appr && <div className="card empty" data-testid="no-approval">No proposal is waiting for approval in this thread. Status: {run?.run?.status} {run?.run?.status_reason ? `(${run.run.status_reason})` : ""}</div>}
      {appr && (
        <div className="grid g2">
          <div className="card">
            <h2>Exactly what will be sent</h2>
            <dl className="kv" data-testid="preview">
              <dt>Bid</dt><dd>{money(appr.payload.bid?.amount)} {appr.payload.bid?.bid_type}</dd>
              <dt>Connects</dt><dd data-testid="preview-connects">{appr.payload.connects_cost} (balance after: {appr.payload.balance_after})</dd>
              <dt>Fit / risk</dt><dd>{appr.payload.fit?.toFixed?.(2)} / {appr.payload.risk?.toFixed?.(2)}</dd>
              <dt>Compliance</dt><dd>{appr.payload.compliance?.allowed ? <Badge v="ok" /> : <Badge v="blocked" />} {(appr.payload.compliance?.fixes_applied || []).join("; ")}</dd>
            </dl>
            <label>Cover letter (edit freely - edits go back through compliance and teach your style memory)</label>
            <textarea value={text} onChange={(e) => setText(e.target.value)} data-testid="draft-text" />
            <label>Reason (for rejections)</label>
            <input value={reason} onChange={(e) => setReason(e.target.value)} data-testid="reject-reason" />
            <div className="row" style={{ marginTop: 12 }}>
              <button className="btn primary" disabled={busy || text !== appr.payload.cover_letter} onClick={() => decide("approve")} data-testid="approve">Approve & submit</button>
              <button className="btn" disabled={busy || text === appr.payload.cover_letter} onClick={() => decide("edit", { edited_text: text })} data-testid="save-edit">Save edit</button>
              <button className="btn danger" disabled={busy} onClick={() => decide("reject", { reason: reason || "not a fit" })} data-testid="reject">Reject</button>
            </div>
            {text !== appr.payload.cover_letter && <p className="sub">You changed the text: save the edit first; the agents re-check it and show the new preview.</p>}
          </div>
          <div className="card">
            <h2>Claims and evidence</h2>
            <div className="sub">Every claim was checked against your portfolio; unsupported ones were removed before review.</div>
            {(draft.claims || []).map((c: any) => (
              <div key={c.id} className="claim" data-testid="claim">
                <Badge v={c.verdict} /> {c.text}
                <div className="sub mono">{(c.evidence_ids || []).map((e: string) => `${evidence[e]?.type || ""}:${evidence[e]?.source || e}`).join(" | ")} {c.note}</div>
              </div>
            ))}
            {(draft.removed_claims || []).length > 0 && <div className="claim"><b>Removed as unsupported:</b> {(draft.removed_claims || []).join(" | ")}</div>}
            <h3 style={{ marginTop: 12 }}>Regenerate one paragraph</h3>
            {paras.map((p: string, i: number) => (
              <div key={i} className="row" style={{ alignItems: "flex-start", margin: "4px 0" }}>
                <button className="btn" disabled={busy} onClick={() => decide("regenerate", { paragraph: i })} data-testid={`regen-${i}`}>Rewrite</button>
                <span className="sub">{p.slice(0, 120)}{p.length > 120 ? "..." : ""}</span>
              </div>
            ))}
            <h3 style={{ marginTop: 12 }}>Critic</h3>
            {(s.critiques || []).map((c: any, i: number) => <div key={i} className="claim">rev {c.revision}: score {c.score}/10 {c.approved ? "approved" : "revise"} - {c.instructions}</div>)}
          </div>
        </div>
      )}
      <div className="card" style={{ marginTop: 14 }}><h2>Agent activity</h2><RunStream threadId={id} onEnd={load} /></div>
      <button className="btn" style={{ marginTop: 12 }} onClick={() => nav(-1)}>Back</button>
    </div>
  );
}
