export type VercelEnvVar = {
  name: string;
  group: string;
  sensitive: boolean;
  environments: string[];
  last_action: string;
  last_updated: string;
  configured_local: boolean;
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

const HIDDEN_LOCAL_ONLY_NAMES = new Set(["OPENAI_MODEL", "DEV_PANEL_SECRET"]);

function visibleLocalOnly(rows: LocalOnlyEnvVar[]): LocalOnlyEnvVar[] {
  return rows.filter(
    (row) => LOCAL_ONLY_NAMES.has(row.name) && !HIDDEN_LOCAL_ONLY_NAMES.has(row.name),
  );
}

type LegacyEnvVar = {
  name: string;
  group: string;
  required?: boolean;
  configured?: boolean;
  configured_local?: boolean;
};

export function normalizeEnvVars(raw: unknown): EnvVarsPayload {
  if (raw && typeof raw === "object" && "vercel_api" in raw) {
    const payload = raw as EnvVarsPayload;
    return {
      ...payload,
      local_only: visibleLocalOnly(payload.local_only ?? []),
    };
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
    local_only: visibleLocalOnly(
      flat
        .filter((v) => LOCAL_ONLY_NAMES.has(v.name))
        .map((v) => ({
          name: v.name,
          group: v.group,
          required: v.required ?? false,
          configured_local: localConfigured(v.name),
        })),
    ),
    vercel_catalog_updated: "2026-08-17",
  };
}
