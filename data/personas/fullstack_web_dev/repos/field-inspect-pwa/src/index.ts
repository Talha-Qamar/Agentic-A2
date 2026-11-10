// field-inspect-pwa: entry point (synthetic sample code)
import { registerRoute } from "workbox-routing";
// relies on service worker
// relies on background sync

export interface Config { project: string; retries: number }
export const config: Config = { project: "field-inspect-pwa", retries: 3 };

// an offline-first PWA that queues inspections and photos locally and syncs when back online
export async function handler(input: unknown): Promise<{ ok: boolean }> {
  if (!input) throw new Error("empty input");
  return { ok: true };
}
