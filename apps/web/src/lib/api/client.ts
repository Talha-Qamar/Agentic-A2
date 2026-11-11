// Typed API client. Request/response types come from src/lib/api/schema.d.ts, generated from the FastAPI OpenAPI
// schema (`npm run gen:api`), so frontend and backend cannot drift silently.
import type { components } from "./schema";

export type Me = components["schemas"]["Me"];
export type JobRow = components["schemas"]["JobRow"];
export type DecisionIn = components["schemas"]["DecisionIn"];
export type SettingsIn = components["schemas"]["SettingsIn"];

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method, credentials: "include",
    headers: body && !(body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
    body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* keep */ }
    throw new ApiError(r.status, msg);
  }
  return r.json() as Promise<T>;
}

export const api = {
  me: () => req<Me>("GET", "/api/auth/me"),
  login: (email: string, password: string) => req<Me>("POST", "/api/auth/login", { email, password }),
  register: (email: string, password: string, name: string) => req<Me>("POST", "/api/auth/register", { email, password, name }),
  logout: () => req<{ ok: boolean }>("POST", "/api/auth/logout"),
  health: () => req<any>("GET", "/api/health"),
  personas: () => req<any[]>("GET", "/api/personas"),
  onboard: (persona: string) => req<any>("POST", "/api/onboarding", { persona }),
  upload: (files: FileList) => { const f = new FormData(); Array.from(files).forEach((x) => f.append("files", x)); return req<any>("POST", "/api/portfolio/upload", f); },
  jobs: () => req<JobRow[]>("GET", "/api/jobs"),
  job: (id: string) => req<any>("GET", `/api/jobs/${encodeURIComponent(id)}`),
  analyse: (id: string, force = false) => req<any>("POST", `/api/jobs/${encodeURIComponent(id)}/analyse`, { force }),
  addJob: (job_id: string) => req<any>("POST", "/api/jobs", { job_id }),
  scout: () => req<any>("POST", "/api/scout/run"),
  searches: () => req<any[]>("GET", "/api/searches"),
  addSearch: (query: string) => req<any>("POST", "/api/searches", { query }),
  delSearch: (id: string) => req<any>("DELETE", `/api/searches/${id}`),
  runs: () => req<any[]>("GET", "/api/runs"),
  run: (id: string) => req<any>("GET", `/api/runs/${encodeURIComponent(id)}`),
  publicTrace: (id: string) => req<any>("GET", `/api/public/traces/${encodeURIComponent(id)}`),
  setPublic: (id: string, pub: boolean) => req<any>("POST", `/api/runs/${encodeURIComponent(id)}/public`, { public: pub }),
  approvals: () => req<any[]>("GET", "/api/approvals"),
  decide: (id: string, d: DecisionIn) => req<any>("POST", `/api/approvals/${encodeURIComponent(id)}`, d),
  pipeline: () => req<any>("GET", "/api/pipeline"),
  syncPipeline: () => req<any>("POST", "/api/pipeline/sync"),
  messages: () => req<any[]>("GET", "/api/messages"),
  draftReply: (tid: string) => req<any>("POST", `/api/messages/${encodeURIComponent(tid)}/draft`),
  analytics: () => req<any>("GET", "/api/analytics"),
  settings: () => req<any>("GET", "/api/settings"),
  saveSettings: (s: SettingsIn) => req<any>("PUT", "/api/settings", s),
  memory: () => req<any>("GET", "/api/memory"),
  forget: (kind: string, key: string) => req<any>("DELETE", `/api/memory/${kind}/${encodeURIComponent(key)}`),
  upworkStart: () => req<{ authorize_url: string }>("GET", "/api/auth/upwork/start"),
  advance: (minutes: number) => req<any>("POST", "/api/demo/advance", { minutes }),
  fault: (down: boolean) => req<any>("POST", "/api/demo/fault", { down }),
};
