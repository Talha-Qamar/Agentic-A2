import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { money } from "../../components/ui";
import { api } from "../../lib/api/client";

export default function PipelinePage() {
  const [p, setP] = useState<any>(null);
  const load = () => api.pipeline().then(setP);
  useEffect(() => { load(); const t = setInterval(load, 8000); return () => clearInterval(t); }, []);
  return (
    <div>
      <div className="head">
        <div><h1>Pipeline</h1><div className="sub">Proposals from submission to outcome. Outcomes feed outcome memory once a category has enough samples.</div></div>
        <div className="row"><button className="btn" onClick={() => api.advance(240).then(() => api.syncPipeline()).then(load)} data-testid="advance-sync">Advance time & sync</button>
          <button className="btn primary" onClick={() => api.syncPipeline().then(load)} data-testid="sync">Sync now</button></div>
      </div>
      <div className="kanban" data-testid="kanban">
        {(p?.stages || []).map((s: string) => (
          <div className="col" key={s}><h3>{s}<span className="badge">{p.columns[s]?.length || 0}</span></h3>
            {(p.columns[s] || []).map((t: any) => (
              <div className="tile" key={t.proposal_id} data-testid="pipeline-tile">
                <div><Link to={`/jobs/${encodeURIComponent(t.job_id)}`}>{t.title || t.job_id}</Link></div>
                <div className="sub">{money(t.bid_amount)} - {t.connects_spent} Connects</div>
                {t.marketplace_thread_id && <Link to="/messages" className="sub">conversation</Link>}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
