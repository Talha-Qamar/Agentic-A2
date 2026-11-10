// live-track: entry point (synthetic sample code)
// relies on redis pub/sub
import mapboxgl from "mapbox-gl";
import * as Location from "expo-location";

export interface Config { project: string; retries: number }
export const config: Config = { project: "live-track", retries: 3 };

// rider apps stream GPS over WebSockets, fanned out through Redis to customer apps with live
export async function handler(input: unknown): Promise<{ ok: boolean }> {
  if (!input) throw new Error("empty input");
  return { ok: true };
}
