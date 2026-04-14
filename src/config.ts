function required(name: string): string {
  const value = process.env[name];
  if (!value || value.trim() === "") {
    throw new Error(`Missing required env var: ${name}`);
  }
  return value.trim();
}

function optional(name: string, fallback: string): string {
  const value = process.env[name];
  return value && value.trim() !== "" ? value.trim() : fallback;
}

function intEnv(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const parsed = Number.parseInt(raw, 10);
  if (Number.isNaN(parsed)) {
    throw new Error(`Invalid integer for env var ${name}: ${raw}`);
  }
  return parsed;
}

export interface Config {
  /** Tebex Plugin API secret key (X-Tebex-Secret header). */
  tebexSecret: string;
  /** Bearer token required by all MCP clients. */
  authToken: string;
  httpHost: string;
  httpPort: number;
}

export function loadConfig(): Config {
  return {
    tebexSecret: required("TEBEX_SECRET"),
    authToken: required("MCP_AUTH_TOKEN"),
    httpHost: optional("HTTP_HOST", "0.0.0.0"),
    httpPort: intEnv("HTTP_PORT", 3000),
  };
}
