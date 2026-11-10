// prospect-notes: entry point (synthetic sample code)
// relies on manifest v3
// relies on service worker
import { defineConfig } from "vite";

export interface Config { project: string; retries: number }
export const config: Config = { project: "prospect-notes", retries: 3 };

// a Manifest V3 extension with a side panel, offline-first storage and sync to a Supabase ba
export async function handler(input: unknown): Promise<{ ok: boolean }> {
  if (!input) throw new Error("empty input");
  return { ok: true };
}
