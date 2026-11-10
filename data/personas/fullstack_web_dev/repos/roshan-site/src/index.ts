// roshan-site: entry point (synthetic sample code)
// relies on groq-queries
/** @type {import("next-sitemap").IConfig} */
// relies on i18n

export interface Config { project: string; retries: number }
export const config: Config = { project: "roshan-site", retries: 3 };

// a Sanity-backed Next.js site with structured content, English/Urdu localisation and WCAG A
export async function handler(input: unknown): Promise<{ ok: boolean }> {
  if (!input) throw new Error("empty input");
  return { ok: true };
}
