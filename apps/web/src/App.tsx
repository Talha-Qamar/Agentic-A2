import { createContext, useContext, useEffect, useState } from "react";
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, Me } from "./lib/api/client";
import LoginPage from "./app/login/page";
import OnboardingPage from "./app/onboarding/page";
import InboxPage from "./app/inbox/page";
import JobPage from "./app/jobs/[id]/page";
import StudioPage from "./app/studio/[id]/page";
import PipelinePage from "./app/pipeline/page";
import MessagesPage from "./app/messages/page";
import RunPage from "./app/runs/[id]/page";
import AnalyticsPage from "./app/analytics/page";
import SettingsPage from "./app/settings/page";

type Ctx = { me: Me | null; refresh: () => Promise<void> };
const AuthCtx = createContext<Ctx>({ me: null, refresh: async () => {} });
export const useAuth = () => useContext(AuthCtx);

function DegradedBanner() {
  const [h, setH] = useState<any>(null);
  useEffect(() => {
    let alive = true;
    const tick = () => api.health().then((x) => alive && setH(x)).catch(() => alive && setH({ degraded: true, marketplace: "API unreachable" }));
    tick();
    const t = setInterval(tick, 15000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  if (!h?.degraded) return null;
  return (
    <div className="banner" data-testid="degraded-banner">
      Marketplace unavailable - GigBid is in degraded mode. Analysis of saved jobs continues; new scouting and all sends are
      paused and queued until it recovers. ({String(h.marketplace).slice(0, 80)})
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const { me } = useAuth();
  const nav = useNavigate();
  const [pending, setPending] = useState(0);
  useEffect(() => {
    const t = () => api.approvals().then((a) => setPending(a.length)).catch(() => {});
    t();
    const i = setInterval(t, 10000);
    return () => clearInterval(i);
  }, []);
  const links: [string, string, number?][] = [["/inbox", "Job inbox", pending], ["/pipeline", "Pipeline"], ["/messages", "Messages"],
    ["/analytics", "Analytics"], ["/settings", "Settings"]];
  return (
    <div className="shell">
      <aside className="side">
        <div className="brand"><i>G</i> GigBid</div>
        <nav className="nav">
          {links.map(([to, label, n]) => (
            <NavLink key={to} to={to} data-testid={`nav-${label.split(" ")[0].toLowerCase()}`}>
              <span>{label}</span>{n ? <span className="badge awaiting_approval">{n}</span> : null}
            </NavLink>
          ))}
        </nav>
        <div className="foot">
          <div>{me?.email}</div>
          <div>persona: {me?.persona}</div>
          <a href="#" onClick={async (e) => { e.preventDefault(); await api.logout(); nav("/login"); window.location.reload(); }}>Sign out</a>
        </div>
      </aside>
      <main className="main"><DegradedBanner />{children}</main>
    </div>
  );
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);
  const loc = useLocation();
  const refresh = async () => { try { setMe(await api.me()); } catch { setMe(null); } };
  useEffect(() => { refresh().finally(() => setReady(true)); }, []);
  if (!ready) return <div className="center sub">Loading...</div>;
  const guard = (el: JSX.Element) => (!me ? <Navigate to="/login" state={{ from: loc.pathname }} /> : !me.onboarded ? <Navigate to="/onboarding" /> : <Shell>{el}</Shell>);
  return (
    <AuthCtx.Provider value={{ me, refresh }}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/onboarding" element={me ? <OnboardingPage /> : <Navigate to="/login" />} />
        <Route path="/inbox" element={guard(<InboxPage />)} />
        <Route path="/jobs/:id" element={guard(<JobPage />)} />
        <Route path="/studio/:id" element={guard(<StudioPage />)} />
        <Route path="/pipeline" element={guard(<PipelinePage />)} />
        <Route path="/messages" element={guard(<MessagesPage />)} />
        <Route path="/runs/:id" element={guard(<RunPage />)} />
        <Route path="/analytics" element={guard(<AnalyticsPage />)} />
        <Route path="/settings" element={guard(<SettingsPage />)} />
        <Route path="*" element={<Navigate to={me ? "/inbox" : "/login"} />} />
      </Routes>
    </AuthCtx.Provider>
  );
}
