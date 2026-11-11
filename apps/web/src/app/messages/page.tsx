import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "../../components/ui";
import { api } from "../../lib/api/client";

export default function MessagesPage() {
  const [convs, setConvs] = useState<any[]>([]);
  const [edit, setEdit] = useState<Record<string, string>>({});
  const load = () => api.messages().then(setConvs);
  useEffect(() => { load(); const t = setInterval(load, 6000); return () => clearInterval(t); }, []);
  const act = async (a: any, action: string, extra: any = {}) => { await api.decide(a.approval_id, { action, ...extra }); setTimeout(load, 1200); };
  return (
    <div>
      <div className="head"><div><h1>Messages</h1><div className="sub">Client replies with suggested responses. Nothing is sent until you approve it.</div></div>
        <button className="btn" onClick={() => api.syncPipeline().then(load)}>Check for new messages</button></div>
      {convs.length === 0 && <div className="card empty">No conversations yet. Clients reply after proposals are submitted (advance time on the Pipeline page).</div>}
      {convs.map((c) => {
        const a = c.pending_approval;
        return (
          <div className="card" key={c.marketplace_thread_id} style={{ marginBottom: 12 }} data-testid="conversation">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h2>{c.title || c.marketplace_thread_id}</h2>
              <div className="row"><Badge v={c.state} />{c.graph_thread_id && <Link to={`/runs/${c.graph_thread_id}`}>trace</Link>}
                <button className="btn" onClick={() => api.draftReply(c.marketplace_thread_id).then(load)}>Redraft</button></div>
            </div>
            {a && (
              <div>
                <div className="claim"><b>Client:</b> {a.payload.client_message}</div>
                <div className="sub">Intent: <Badge v={a.payload.intent?.intent} /> {a.payload.intent?.injection_detected && <Badge v="blocked" />}</div>
                <label>Suggested reply</label>
                <textarea style={{ minHeight: 120 }} value={edit[a.approval_id] ?? a.payload.text} onChange={(e) => setEdit({ ...edit, [a.approval_id]: e.target.value })} data-testid="reply-text" />
                <div className="row" style={{ marginTop: 8 }}>
                  {(edit[a.approval_id] ?? a.payload.text) === a.payload.text
                    ? <button className="btn primary" onClick={() => act(a, "approve")} data-testid="approve-reply">Approve & send</button>
                    : <button className="btn" onClick={() => act(a, "edit", { edited_text: edit[a.approval_id] })}>Save edit</button>}
                  <button className="btn danger" onClick={() => act(a, "reject", { reason: "not now" })}>Discard</button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
