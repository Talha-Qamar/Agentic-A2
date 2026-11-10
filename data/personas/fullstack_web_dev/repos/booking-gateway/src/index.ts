// booking-gateway: entry point (synthetic sample code)
import DataLoader from "dataloader";
import { createClient } from "redis";
import http from "k6/http";

export interface Config { project: string; retries: number }
export const config: Config = { project: "booking-gateway", retries: 3 };

// a GraphQL gateway with batched resolvers and response caching in front of the legacy servi
export async function handler(input: unknown): Promise<{ ok: boolean }> {
  if (!input) throw new Error("empty input");
  return { ok: true };
}
