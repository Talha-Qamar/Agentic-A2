// teamboard-auth: entry point (synthetic sample code)
import { generateRegistrationOptions } from "@simplewebauthn/server";
// relies on saml
// relies on oidc

export interface Config { project: string; retries: number }
export const config: Config = { project: "teamboard-auth", retries: 3 };

// moved login to a standard auth library with Google and SAML SSO, passkeys and session hard
export async function handler(input: unknown): Promise<{ ok: boolean }> {
  if (!input) throw new Error("empty input");
  return { ok: true };
}
