"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Server,
  Shield,
  XCircle,
} from "lucide-react";

import { normalizeEnvVars } from "../../lib/dev-panel-env";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SECRET_STORAGE_KEY = "dev_panel_secret";

type HealthStatus = "up" | "down" | "checking";

type HealthTarget = {
  id: string;
  label: string;
  url: string;
  path: string;
};

type AuditEvent = {
  type: string;
  timestamp: string;
  identity?: string;
  content_hash?: string;
  version?: number;
  git_commit?: string;
  file_count?: number;
  [key: string]: unknown;
};

type KnowledgeSource = {
  identity: string;
  content_hash: string;
  version: number;
  byte_size: number;
  status: string;
  audited_at?: string;
  updated_at?: string;
  file_modified_at?: string;
  git_added_at?: string;
  git_last_committed_at?: string;
  git_last_commit?: string;
  stale_at?: string;
};

type LeadRecord = {
  timestamp: string;
  name: string;
  email: string;
  question: string;
  whatsapp: string;
};

type DevPanelData = {
  env_vars: ReturnType<typeof normalizeEnvVars>;
  knowledge: {
    state: {
      last_sync?: string;
      git_commit?: string;
    };
    sources_current: KnowledgeSource[];
    sources_stale: KnowledgeSource[];
    events: AuditEvent[];
  };
  leads?: {
    window_days: number;
    items: LeadRecord[];
  };
  dev_panel_secret_required: boolean;
};

type SmokeCheck = {
  id: string;
  name: string;
  group: string;
  status: "pass" | "fail" | "skip";
  required: boolean;
  detail: string;
};

type SmokeResult = {
  ok: boolean;
  ran_at?: string;
  summary?: { passed: number; failed: number; skipped: number; total: number };
  checks: SmokeCheck[];
  notes?: string[];
};

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function shortHash(hash: string): string {
  const bare = hash.replace(/^sha256:/, "");
  return bare.length > 16 ? `${bare.slice(0, 12)}…` : bare;
}

function formatPanelTimestamp(iso: string): string {
  const match = iso.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
  if (match) return `${match[1]} ${match[2]}`;
  const offsetMatch = iso.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  if (offsetMatch) return `${offsetMatch[1]} ${offsetMatch[2]}`;
  return iso;
}

function formatVercelDate(iso: string, action: string): string {
  const d = new Date(`${iso}T00:00:00`);
  const label = d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  return `${action} ${label}`;
}

function ConfiguredBadge({ configured }: { configured: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs ${
        configured ? "bg-accent-muted text-accent" : "bg-red-500/10 text-red-400"
      }`}
    >
      {configured ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
      {configured ? "Configured" : "Missing"}
    </span>
  );
}

function buildHealthTargets(origin?: string): HealthTarget[] {
  const prodApi = process.env.NEXT_PUBLIC_PRODUCTION_API_URL?.replace(/\/$/, "");
  const prodFe = process.env.NEXT_PUBLIC_PRODUCTION_FRONTEND_URL?.replace(/\/$/, "");
  const configuredApi = API_BASE.replace(/\/$/, "");

  const targets: HealthTarget[] = [
    { id: "api-configured", label: "Backend (NEXT_PUBLIC_API_URL)", url: configuredApi, path: "/healthz" },
  ];

  if (origin) {
    const isLocal = origin.includes("localhost");
    if (isLocal && configuredApi !== "http://localhost:8000") {
      targets.push({
        id: "api-local",
        label: "Backend (localhost:8000)",
        url: "http://localhost:8000",
        path: "/healthz",
      });
    }
    targets.push({
      id: "fe-current",
      label: isLocal ? "Frontend (localhost:3000)" : "Frontend (this deployment)",
      url: isLocal ? "http://localhost:3000" : origin,
      path: "/",
    });
  }

  if (prodApi) {
    targets.push({ id: "vercel-api", label: "Vercel API", url: prodApi, path: "/healthz" });
  }
  if (prodFe) {
    targets.push({ id: "vercel-fe", label: "Vercel Frontend", url: prodFe, path: "/" });
  }

  return targets;
}

function StatusDot({ status }: { status: HealthStatus }) {
  if (status === "checking") {
    return <Loader2 size={14} className="animate-spin text-text-muted" />;
  }
  if (status === "up") {
    return <CheckCircle2 size={14} className="text-accent" />;
  }
  return <XCircle size={14} className="text-red-400" />;
}

export default function DevPanelPage() {
  const [secret, setSecret] = useState("");
  const [secretInput, setSecretInput] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadBusy, setReloadBusy] = useState(false);
  const [smokeBusy, setSmokeBusy] = useState(false);
  const [smoke, setSmoke] = useState<SmokeResult | null>(null);
  const [data, setData] = useState<DevPanelData | null>(null);
  const [health, setHealth] = useState<Record<string, { status: HealthStatus; ms?: number }>>({});
  const [healthTargets, setHealthTargets] = useState<HealthTarget[]>([]);
  const [mounted, setMounted] = useState(false);

  const checkHealth = useCallback(async (targets: HealthTarget[]) => {
    if (targets.length === 0) return;

    const next: Record<string, { status: HealthStatus; ms?: number }> = {};
    for (const target of targets) {
      next[target.id] = { status: "checking" };
    }
    setHealth(next);

    await Promise.all(
      targets.map(async (target) => {
        const start = performance.now();
        try {
          const res = await fetch(`${target.url}${target.path}`, {
            method: "GET",
            cache: "no-store",
            signal: AbortSignal.timeout(8000),
          });
          const ms = Math.round(performance.now() - start);
          setHealth((prev) => ({
            ...prev,
            [target.id]: { status: res.ok ? "up" : "down", ms },
          }));
        } catch {
          const ms = Math.round(performance.now() - start);
          setHealth((prev) => ({
            ...prev,
            [target.id]: { status: "down", ms },
          }));
        }
      }),
    );
  }, []);

  const fetchPanel = useCallback(async (panelSecret: string) => {
    setLoading(true);
    setAuthError(null);
    try {
      const headers: HeadersInit = {};
      if (panelSecret) headers["X-Dev-Panel-Secret"] = panelSecret;

      const res = await fetch(`${API_BASE}/api/dev/status`, { headers, cache: "no-store" });
      if (res.status === 401) {
        setAuthError("Invalid or missing dev panel secret.");
        setData(null);
        sessionStorage.removeItem(SECRET_STORAGE_KEY);
        return;
      }
      if (!res.ok) {
        if (res.status === 404) {
          throw new Error(
            "Backend is missing /api/dev/status — restart uvicorn so it loads the latest code.",
          );
        }
        throw new Error(`API returned ${res.status}`);
      }
      const raw = await res.json();
      const payload: DevPanelData = {
        ...raw,
        env_vars: normalizeEnvVars(raw.env_vars),
      };
      setData(payload);
      if (panelSecret) sessionStorage.setItem(SECRET_STORAGE_KEY, panelSecret);
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : "Failed to load dev panel");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshAll = useCallback(
    async (panelSecret: string, targets: HealthTarget[]) => {
      await Promise.all([checkHealth(targets), fetchPanel(panelSecret)]);
    },
    [checkHealth, fetchPanel],
  );

  useEffect(() => {
    const stored = sessionStorage.getItem(SECRET_STORAGE_KEY) ?? "";
    const targets = buildHealthTargets(window.location.origin);
    setSecret(stored);
    setHealthTargets(targets);
    setMounted(true);
    void refreshAll(stored, targets);
  }, [refreshAll]);

  const handleRefresh = () => {
    void refreshAll(secret, healthTargets);
  };

  const handleUnlock = (e: React.FormEvent) => {
    e.preventDefault();
    const next = secretInput.trim();
    setSecret(next);
    void fetchPanel(next);
  };

  const handleRunSmoke = async () => {
    setSmokeBusy(true);
    setSmoke(null);
    try {
      const headers: HeadersInit = { "Content-Type": "application/json" };
      if (secret) headers["X-Dev-Panel-Secret"] = secret;
      const res = await fetch(`${API_BASE}/api/dev/smoke`, {
        method: "POST",
        headers,
        cache: "no-store",
      });
      if (res.status === 401) {
        setAuthError("Invalid or missing dev panel secret.");
        return;
      }
      if (res.status === 404) {
        throw new Error("Backend is missing /api/dev/smoke — restart uvicorn so it loads the latest code.");
      }
      if (!res.ok) {
        throw new Error(`Smoke test returned ${res.status}`);
      }
      setSmoke((await res.json()) as SmokeResult);
    } catch (err) {
      setSmoke({
        ok: false,
        checks: [],
        notes: [err instanceof Error ? err.message : "Smoke test request failed"],
      });
    } finally {
      setSmokeBusy(false);
    }
  };

  const handleReloadKnowledge = async () => {
    setReloadBusy(true);
    try {
      const headers: HeadersInit = { "Content-Type": "application/json" };
      if (secret) headers["X-Dev-Panel-Secret"] = secret;
      await fetch(`${API_BASE}/api/knowledge/reload`, { method: "POST", headers });
      await fetchPanel(secret);
    } finally {
      setReloadBusy(false);
    }
  };

  const vercelEnvVars = data?.env_vars.vercel_api ?? [];

  const showUnlock = authError === "Invalid or missing dev panel secret." && !data;

  if (showUnlock) {
    return (
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center px-6 py-16">
        <div className="rounded-xl border border-border bg-surface p-8">
          <div className="mb-6 flex items-center gap-3">
            <Shield size={22} className="text-accent" />
            <h1 className="font-display text-2xl text-text-primary">Developer panel</h1>
          </div>
          <p className="mb-6 text-sm leading-relaxed text-text-secondary">
            Enter the <code className="text-accent">DEV_PANEL_SECRET</code> from the API environment.
            Values are never shown — only names and configured status.
          </p>
          <form onSubmit={handleUnlock} className="space-y-4">
            <input
              type="password"
              value={secretInput}
              onChange={(e) => setSecretInput(e.target.value)}
              placeholder="Dev panel secret"
              className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm text-text-primary outline-none focus:border-accent/60"
              autoComplete="off"
            />
            {authError && (
              <p className="flex items-center gap-2 text-sm text-red-400">
                <AlertCircle size={14} />
                {authError}
              </p>
            )}
            <button
              type="submit"
              className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-background hover:opacity-90"
            >
              Unlock
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-10 lg:px-12">
      <div className="mb-10 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-text-primary">Developer panel</h1>
          <p className="mt-2 text-sm text-text-secondary">
            Environment, deployment health, and knowledge audit. Not linked in public nav.
          </p>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-text-secondary transition-colors hover:border-accent/50 hover:text-text-primary disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {authError && !showUnlock && (
        <div className="mb-8 flex items-start gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <p>{authError}</p>
        </div>
      )}

      {/* Services */}
      <section className="mb-10">
        <h2 className="mb-4 flex items-center gap-2 text-sm font-medium uppercase tracking-wider text-text-muted">
          <Server size={14} />
          Services
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {!mounted ? (
            <div className="rounded-lg border border-border bg-surface/60 px-4 py-3 text-sm text-text-muted">
              Checking services…
            </div>
          ) : (
            healthTargets.map((target) => {
            const h = health[target.id];
            return (
              <div
                key={target.id}
                className="rounded-lg border border-border bg-surface/60 px-4 py-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm text-text-primary">{target.label}</span>
                  <StatusDot status={h?.status ?? "checking"} />
                </div>
                <p className="mt-1 truncate font-mono text-xs text-text-muted">
                  {target.url}
                  {target.path}
                </p>
                {h?.ms !== undefined && (
                  <p className="mt-1 text-xs text-text-secondary">{h.ms} ms</p>
                )}
              </div>
            );
          })
          )}
        </div>
      </section>

      {/* Config smoke test */}
      <section className="mb-10">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium uppercase tracking-wider text-text-muted">
              Configuration smoke test
            </h2>
            <p className="mt-1 text-xs text-text-secondary">
              Checks env presence and live OpenAI, Tavily, WhatsApp, knowledge, and the agent.
              WhatsApp sends a real test message to <span className="font-mono">TWILIO_WHATSAPP_TO</span>.
              There is no email path in production.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void handleRunSmoke()}
            disabled={smokeBusy || !data}
            className="rounded-lg border border-border px-3 py-1.5 text-xs text-text-secondary hover:border-accent/50 disabled:opacity-50"
          >
            {smokeBusy ? "Running…" : "Run smoke test"}
          </button>
        </div>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-border bg-surface/80 text-text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Check</th>
                <th className="px-4 py-3 font-medium">Group</th>
                <th className="px-4 py-3 font-medium">Required</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {!smoke && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-text-muted">
                    {smokeBusy ? "Running live checks…" : "Click Run smoke test to verify OpenAI, Tavily, WhatsApp, and knowledge."}
                  </td>
                </tr>
              )}
              {(smoke?.checks ?? []).map((row) => (
                <tr key={row.id} className="bg-surface/30">
                  <td className="px-4 py-2.5 font-mono text-xs text-text-primary">{row.name}</td>
                  <td className="px-4 py-2.5 text-text-secondary">{row.group}</td>
                  <td className="px-4 py-2.5 text-xs text-text-secondary">{row.required ? "Yes" : "No"}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        row.status === "pass"
                          ? "bg-accent-muted text-accent"
                          : row.status === "fail"
                            ? "bg-red-500/10 text-red-400"
                            : "bg-surface text-text-muted"
                      }`}
                    >
                      {row.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-text-secondary">{row.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {smoke && (
          <p className="mt-3 text-xs text-text-secondary">
            {smoke.ok ? "Required checks passed." : "One or more required checks failed."}
            {smoke.summary && (
              <>
                {" "}
                {smoke.summary.passed} passed · {smoke.summary.failed} failed · {smoke.summary.skipped} skipped
              </>
            )}
          </p>
        )}
        {(smoke?.notes ?? []).map((note) => (
          <p key={note} className="mt-1 text-xs text-text-muted">
            {note}
          </p>
        ))}
      </section>

      {/* Env vars */}
      <section className="mb-10">
        <div className="mb-4">
          <h2 className="text-sm font-medium uppercase tracking-wider text-text-muted">
            Secrets &amp; environment variables
          </h2>
          {data?.env_vars.vercel_catalog_updated && (
            <p className="mt-1 text-xs text-text-secondary">
              Vercel catalog snapshot {data.env_vars.vercel_catalog_updated}. Values are never shown.
            </p>
          )}
        </div>

        <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-muted">
          Vercel API project
        </h3>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-border bg-surface/80 text-text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Group</th>
                <th className="px-4 py-3 font-medium">Secret</th>
                <th className="px-4 py-3 font-medium">Vercel envs</th>
                <th className="px-4 py-3 font-medium">Last Vercel update</th>
                <th className="px-4 py-3 font-medium">On Vercel</th>
                <th className="px-4 py-3 font-medium">Local .env</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {vercelEnvVars.map((row) => (
                <tr key={row.name} className="bg-surface/30">
                  <td className="px-4 py-2.5 font-mono text-xs text-text-primary">{row.name}</td>
                  <td className="px-4 py-2.5 text-text-secondary">{row.group}</td>
                  <td className="px-4 py-2.5 text-xs text-text-secondary">
                    {row.sensitive ? "Yes" : "No"}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-text-secondary">
                    {row.environments.join(", ")}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-xs text-text-secondary">
                    {formatVercelDate(row.last_updated, row.last_action)}
                  </td>
                  <td className="px-4 py-2.5">
                    <ConfiguredBadge configured={true} />
                  </td>
                  <td className="px-4 py-2.5">
                    <ConfiguredBadge configured={row.configured_local} />
                  </td>
                </tr>
              ))}
              {!data && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-text-muted">
                    {loading ? "Loading…" : "Connect to backend to load Vercel catalog"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Knowledge sources */}
      <section className="mb-10">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium uppercase tracking-wider text-text-muted">
              Knowledge directory
            </h2>
            {data?.knowledge.state.last_sync && (
              <p className="mt-1 text-xs text-text-secondary">
                Last sync {formatPanelTimestamp(data.knowledge.state.last_sync)} · Git{" "}
                <span className="font-mono">{data.knowledge.state.git_commit?.slice(0, 7) ?? "—"}</span>
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={() => void handleReloadKnowledge()}
            disabled={reloadBusy || !data}
            className="rounded-lg border border-border px-3 py-1.5 text-xs text-text-secondary hover:border-accent/50 disabled:opacity-50"
          >
            {reloadBusy ? "Reloading…" : "Re-run audit"}
          </button>
        </div>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[800px] text-left text-sm">
            <thead className="border-b border-border bg-surface/80 text-text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">File</th>
                <th className="px-4 py-3 font-medium">Version</th>
                <th className="px-4 py-3 font-medium">Size</th>
                <th className="px-4 py-3 font-medium">Hash</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Git added</th>
                <th className="px-4 py-3 font-medium">Git last commit</th>
                <th className="px-4 py-3 font-medium">File modified</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(data?.knowledge.sources_current ?? []).map((src) => (
                <tr key={src.identity} className="bg-surface/30">
                  <td className="px-4 py-2.5 font-mono text-xs text-text-primary">{src.identity}</td>
                  <td className="px-4 py-2.5 text-text-secondary">v{src.version}</td>
                  <td className="px-4 py-2.5 text-text-secondary">{formatBytes(src.byte_size)}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-text-muted" title={src.content_hash}>
                    {shortHash(src.content_hash)}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="rounded-full bg-accent-muted px-2 py-0.5 text-xs text-accent">
                      {src.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-text-secondary">
                    {src.git_added_at ? formatPanelTimestamp(src.git_added_at) : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-text-secondary">
                    {src.git_last_committed_at ? (
                      <>
                        {formatPanelTimestamp(src.git_last_committed_at)}
                        {src.git_last_commit && (
                          <span className="ml-1 font-mono text-text-muted">
                            ({src.git_last_commit.slice(0, 7)})
                          </span>
                        )}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-text-secondary">
                    {src.file_modified_at ? formatPanelTimestamp(src.file_modified_at) : "—"}
                  </td>
                </tr>
              ))}
              {(data?.knowledge.sources_stale ?? []).map((src) => (
                <tr key={`stale-${src.identity}`} className="bg-surface/30 opacity-70">
                  <td className="px-4 py-2.5 font-mono text-xs text-text-primary">{src.identity}</td>
                  <td className="px-4 py-2.5 text-text-secondary">v{src.version}</td>
                  <td className="px-4 py-2.5 text-text-secondary">{formatBytes(src.byte_size)}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-text-muted" title={src.content_hash}>
                    {shortHash(src.content_hash)}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-xs text-red-400">
                      stale
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-text-secondary" colSpan={3}>
                    {src.stale_at ? `Removed ${formatPanelTimestamp(src.stale_at)}` : "—"}
                  </td>
                </tr>
              ))}
              {!data && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-text-muted">
                    {loading ? "Loading…" : authError ?? "No data — check backend and secret"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Audit events */}
      <section>
        <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
          Audit log ({data?.knowledge.events.length ?? 0} events)
        </h2>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-border bg-surface/80 text-text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">Event</th>
                <th className="px-4 py-3 font-medium">File</th>
                <th className="px-4 py-3 font-medium">Version</th>
                <th className="px-4 py-3 font-medium">Git</th>
                <th className="px-4 py-3 font-medium">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(data?.knowledge.events ?? []).length === 0 && !loading && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-text-muted">
                    {authError ?? "No audit events yet"}
                  </td>
                </tr>
              )}
              {(data?.knowledge.events ?? [])
                .slice()
                .reverse()
                .map((event, idx) => (
                  <tr key={`${event.timestamp}-${idx}`} className="bg-surface/30">
                    <td className="whitespace-nowrap px-4 py-2.5 text-xs text-text-secondary">
                      {formatPanelTimestamp(event.timestamp)}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-accent">{event.type}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-text-primary">
                      {event.identity ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-text-secondary">
                      {event.version !== undefined ? `v${event.version}` : "—"}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-text-muted">
                      {typeof event.git_commit === "string" ? event.git_commit.slice(0, 7) : "—"}
                    </td>
                    <td className="max-w-xs truncate px-4 py-2.5 font-mono text-xs text-text-muted">
                      {event.content_hash
                        ? shortHash(event.content_hash)
                        : event.file_count !== undefined
                          ? `${event.file_count} files`
                          : "—"}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Recent leads */}
      <section className="mt-10">
        <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
          Leads (last {data?.leads?.window_days ?? 7} days)
        </h2>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-border bg-surface/80 text-text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Question</th>
                <th className="px-4 py-3 font-medium">WhatsApp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(data?.leads?.items ?? []).length === 0 && !loading && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-text-muted">
                    No leads in the last {data?.leads?.window_days ?? 7} days
                  </td>
                </tr>
              )}
              {(data?.leads?.items ?? []).map((lead, idx) => (
                <tr key={`${lead.timestamp}-${lead.email}-${idx}`} className="bg-surface/30">
                  <td className="whitespace-nowrap px-4 py-2.5 text-xs text-text-secondary">
                    {formatPanelTimestamp(lead.timestamp)}
                  </td>
                  <td className="px-4 py-2.5 text-sm text-text-primary">{lead.name || "—"}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-text-secondary">
                    {lead.email || "—"}
                  </td>
                  <td className="max-w-md px-4 py-2.5 text-sm text-text-primary">{lead.question || "—"}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs ${
                        lead.whatsapp === "sent"
                          ? "bg-accent-muted text-accent"
                          : "bg-red-500/10 text-red-400"
                      }`}
                    >
                      {lead.whatsapp === "sent" ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
                      {lead.whatsapp || "unknown"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
