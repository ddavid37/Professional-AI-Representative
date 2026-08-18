export type VercelEnvVar = {
  name: string;
  group: string;
  sensitive: boolean;
  environments: string[];
  last_action: string;
  last_updated: string;
  configured_local: boolean;
  note?: string;
};

export type LocalOnlyEnvVar = {
  name: string;
  group: string;
  required: boolean;
  configured_local: boolean;
};

export type EnvVarsPayload = {
  vercel_api: VercelEnvVar[];
  local_only: LocalOnlyEnvVar[];
  vercel_catalog_updated: string;
};

/** Matches backend VERCEL_API_ENV_CATALOG — used if API returns legacy flat list. */
const VERCEL_API_CATALOG: Omit<VercelEnvVar, "configured_local">[] = [
  {
    name: "OPENAI_API_KEY",
    group: "OpenAI",
    sensitive: true,
    environments: ["Production", "Preview"],
    last_action: "Updated",
    last_updated: "2026-05-05",
  },
  {
    name: "NEXT_PUBLIC_API_URL",
    group: "Frontend",
    sensitive: true,
    environments: ["Production"],
    last_action: "Added",
    last_updated: "2026-06-04",
    note: "Set on API project today; belongs on the frontend Vercel project.",
  },
  {
    name: "TWILIO_ACCOUNT_SID",
    group: "Twilio",
    sensitive: true,
    environments: ["Production"],
    last_action: "Added",
    last_updated: "2026-06-05",
  },
  {
    name: "TWILIO_AUTH_TOKEN",
    group: "Twilio",
    sensitive: true,
    environments: ["Production"],
    last_action: "Added",
    last_updated: "2026-06-05",
  },
  {
    name: "TWILIO_WHATSAPP_FROM",
    group: "Twilio",
    sensitive: false,
    environments: ["Production"],
    last_action: "Added",
    last_updated: "2026-06-05",
  },
  {
    name: "TWILIO_WHATSAPP_TO",
    group: "Twilio",
    sensitive: false,
    environments: ["Production"],
    last_action: "Added",
    last_updated: "2026-06-05",
  },
  {
    name: "TAVILY_API_KEY",
    group: "Tavily",
    sensitive: true,
    environments: ["Production", "Preview"],
    last_action: "Added",
    last_updated: "2026-08-12",
  },
];

const LOCAL_ONLY_NAMES = new Set([
  "CRON_SECRET",
  "LINKEDIN_PROFILE_URL",
  "LINKEDIN_BIO_SOURCE",
  "LINKEDIN_BIO_FILE",
  "LINKEDIN_BIO_EXPORT_URL",
]);

type LegacyEnvVar = {
  name: string;
  group: string;
  required?: boolean;
  configured?: boolean;
  configured_local?: boolean;
};

export function normalizeEnvVars(raw: unknown): EnvVarsPayload {
  if (raw && typeof raw === "object" && "vercel_api" in raw) {
    return raw as EnvVarsPayload;
  }

  const flat: LegacyEnvVar[] = Array.isArray(raw) ? raw : [];
  const byName = new Map(flat.map((v) => [v.name, v]));

  const localConfigured = (name: string) => {
    const row = byName.get(name);
    return Boolean(row?.configured_local ?? row?.configured);
  };

  return {
    vercel_api: VERCEL_API_CATALOG.map((spec) => ({
      ...spec,
      configured_local: localConfigured(spec.name),
    })),
    local_only: flat
      .filter((v) => LOCAL_ONLY_NAMES.has(v.name))
      .map((v) => ({
        name: v.name,
        group: v.group,
        required: v.required ?? false,
        configured_local: localConfigured(v.name),
      })),
    vercel_catalog_updated: "2026-08-17",
  };
}

export function countSecretStatus(env: EnvVarsPayload): {
  onVercel: number;
  configuredLocal: number;
  missingLocal: string[];
} {
  const sensitive = env.vercel_api.filter((v) => v.sensitive);
  const missingLocal = sensitive.filter((v) => !v.configured_local).map((v) => v.name);

  return {
    onVercel: sensitive.length,
    configuredLocal: sensitive.filter((v) => v.configured_local).length,
    missingLocal,
  };
}
