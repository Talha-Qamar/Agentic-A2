// zari-headless: entry point (synthetic sample code)
import { gql } from "graphql-tag";
// relies on ISR
// relies on lighthouse-ci

export interface Config { project: string; retries: number }
export const config: Config = { project: "zari-headless", retries: 3 };

// a headless Next.js storefront with incremental static regeneration, image optimisation and
export async function handler(input: unknown): Promise<{ ok: boolean }> {
  if (!input) throw new Error("empty input");
  return { ok: true };
}
