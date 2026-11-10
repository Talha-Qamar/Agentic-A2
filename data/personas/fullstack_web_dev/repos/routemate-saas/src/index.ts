// routemate-saas: entry point (synthetic sample code)
import { z } from "zod";
import { initTRPC } from "@trpc/server";
// relies on row-level security

export interface Config { project: string; retries: number }
export const config: Config = { project: "routemate-saas", retries: 3 };

// a single multi-tenant Next.js app with tenant-scoped queries, role-based permissions and s
export async function handler(input: unknown): Promise<{ ok: boolean }> {
  if (!input) throw new Error("empty input");
  return { ok: true };
}
