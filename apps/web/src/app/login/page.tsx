import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../App";
import { api } from "../../lib/api/client";

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  const { refresh } = useAuth();
  const nav = useNavigate();
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    try {
      if (mode === "login") await api.login(email, password); else await api.register(email, password, name);
      await refresh();
      nav("/inbox");
    } catch (x: any) { setErr(x.message); }
  };
  return (
    <div className="center">
      <form className="card auth" onSubmit={submit}>
        <div className="brand"><i>G</i> GigBid</div>
        <p className="sub">Your freelance bidding team: it finds jobs, checks fit and risk, drafts grounded proposals, and waits for your approval before anything is sent.</p>
        <div className="tabs">
          <button type="button" className={`btn ${mode === "login" ? "primary" : ""}`} onClick={() => setMode("login")}>Sign in</button>
          <button type="button" className={`btn ${mode === "register" ? "primary" : ""}`} onClick={() => setMode("register")}>Create account</button>
        </div>
        {mode === "register" && (<><label>Name</label><input value={name} onChange={(e) => setName(e.target.value)} required /></>)}
        <label>Email</label><input data-testid="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <label>Password</label><input data-testid="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {err && <p style={{ color: "var(--bad)" }} data-testid="login-error">{err}</p>}
        <button className="btn primary" style={{ marginTop: 14, width: "100%" }} data-testid="login-submit">{mode === "login" ? "Sign in" : "Create account"}</button>
      </form>
    </div>
  );
}
