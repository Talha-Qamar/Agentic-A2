// support-widget: entry point (synthetic sample code)
import { streamText } from "ai";
// relies on streaming
// relies on rate limiting

export interface Config { project: string; retries: number }
export const config: Config = { project: "support-widget", retries: 3 };

// an embedded chat widget with streaming answers grounded in help articles and a handoff to 
export async function handler(input: unknown): Promise<{ ok: boolean }> {
  if (!input) throw new Error("empty input");
  return { ok: true };
}
