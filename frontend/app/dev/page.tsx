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
  dev_panel_secret_required: boolean;
  linkedin_bio?: LinkedInBioStatus;
};

type LinkedInBioStatus = {
  id: string;
  type: string;
  path: string;
  identity: string;
  status: string;
  version?: number;
  content_hash?: string;
  last_synced_at?: string;
  last_changed_at?: string;
  profile_url?: string;
  source_mode?: string;
};

type LinkedInSyncResponse = {
  ok: boolean;
  result: string;
  trigger: string;
  previous_version?: number;
  new_version?: number;
  change_summary?: string;
  message?: string;
  error_category?: string;
  agent_reloaded?: boolean;
  last_synced_at?: string;
  linkedin_bio?: LinkedInBioStatus;
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

function linkedinStatusFromPanel(data: DevPanelData | null): LinkedInBioStatus | undefined {
  if (data?.linkedin_bio?.identity) return data.linkedin_bio;
  const src = data?.knowledge.sources_current.find((s) => s.identity === "LinkedIn_Bio.md");
  if (!src) return undefined;
  return {
    id: "linkedin_bio",
    type: "linkedin",
    path: "knowledge/LinkedIn_Bio.md",
    identity: src.identity,
    status: src.status,
    version: src.version,
    content_hash: src.content_hash,
    last_changed_at: src.audited_at ?? src.updated_at,
  };
}

function formatLinkedInSyncError(sync: LinkedInSyncResponse): string {
  if (sync.error_category === "provider_not_configured") {
    return "No authorized About/Bio export is configured yet, so nothing was fetched. The current knowledge file was not changed.";
  }
  if (sync.error_category === "linkedin_host_blocked") {
    return "LinkedIn pages are not fetched directly. Use a file or export URL you control.";
  }
  if (sync.error_category === "empty_bio") {
    return "The export was empty, so the current knowledge file was kept.";
  }
  if (sync.error_category === "knowledge_not_writable") {
    return "The knowledge file could not be written (read-only environment). Current knowledge was kept.";
  }
  return sync.message || "Sync failed. Current knowledge was kept.";
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
  const [linkedinBusy, setLinkedinBusy] = useState(false);
  const [linkedinSync, setLinkedinSync] = useState<LinkedInSyncResponse | null>(null);
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

  const handleLinkedInSync = async () => {
    setLinkedinBusy(true);
    setLinkedinSync(null);
    try {
      const headers: HeadersInit = { "Content-Type": "application/json" };
      if (secret) headers["X-Dev-Panel-Secret"] = secret;
      const res = await fetch(`${API_BASE}/internal/knowledge/sync/linkedin-bio`, {
        method: "POST",
        headers,
        cache: "no-store",
      });
      if (res.status === 401) {
        setAuthError("Invalid or missing dev panel secret.");
        return;
      }
      const payload = (await res.json()) as LinkedInSyncResponse;
      setLinkedinSync(payload);
      await fetchPanel(secret);
    } catch (err) {
      setLinkedinSync({
        ok: false,
        result: "failed",
        trigger: "manual",
        message: err instanceof Error ? err.message : "Sync request failed",
      });
    } finally {
      setLinkedinBusy(false);
    }
  };

  const vercelEnvVars = data?.env_vars.vercel_api ?? [];
  const localOnlyEnvVars = data?.env_vars.local_only ?? [];

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
                  <td className="px-4 py-2.5">
                    <div className="font-mono text-xs text-text-primary">{row.name}</div>
                    {row.note && (
                      <div className="mt-1 text-xs text-amber-400/90">{row.note}</div>
                    )}
                  </td>
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

        {localOnlyEnvVars.length > 0 && (
          <div className="mt-6">
            <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-muted">
              Local / not on Vercel API yet
            </h3>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="border-b border-border bg-surface/80 text-text-muted">
                  <tr>
                    <th className="px-4 py-3 font-medium">Name</th>
                    <th className="px-4 py-3 font-medium">Group</th>
                    <th className="px-4 py-3 font-medium">Secret</th>
                    <th className="px-4 py-3 font-medium">Required locally</th>
                    <th className="px-4 py-3 font-medium">Local .env</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {localOnlyEnvVars.map((row) => (
                    <tr key={row.name} className="bg-surface/30">
                      <td className="px-4 py-2.5 font-mono text-xs text-text-primary">{row.name}</td>
                      <td className="px-4 py-2.5 text-text-secondary">{row.group}</td>
                      <td className="px-4 py-2.5 text-xs text-text-secondary">
                        {row.name === "CRON_SECRET" ? "Yes" : "No"}
                      </td>
                      <td className="px-4 py-2.5 text-text-secondary">{row.required ? "Yes" : "No"}</td>
                      <td className="px-4 py-2.5">
                        <ConfiguredBadge configured={row.configured_local} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* LinkedIn Bio sync */}
      <section className="mb-10">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium uppercase tracking-wider text-text-muted">
              LinkedIn Bio
            </h2>
            <p className="mt-1 text-xs text-text-secondary">
              Syncs About/Bio only into <span className="font-mono">knowledge/LinkedIn_Bio.md</span>.
              Does not scrape LinkedIn.com.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void handleLinkedInSync()}
            disabled={linkedinBusy || !data}
            className="rounded-lg border border-border px-3 py-1.5 text-xs text-text-secondary hover:border-accent/50 disabled:opacity-50"
          >
            {linkedinBusy ? "Syncing…" : "Sync LinkedIn Bio"}
          </button>
        </div>
        <div className="rounded-lg border border-border bg-surface/60 px-4 py-4">
          {(() => {
            const bio = linkedinStatusFromPanel(data);
            return (
              <dl className="grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs uppercase tracking-wide text-text-muted">Status</dt>
                  <dd className="text-text-primary">{bio?.status ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-text-muted">Knowledge version</dt>
                  <dd className="text-text-primary">{bio?.version != null ? `v${bio.version}` : "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-text-muted">Last synced</dt>
                  <dd className="text-text-secondary">
                    {bio?.last_synced_at ? formatPanelTimestamp(bio.last_synced_at) : "Never"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-text-muted">Last changed</dt>
                  <dd className="text-text-secondary">
                    {bio?.last_changed_at ? formatPanelTimestamp(bio.last_changed_at) : "—"}
                  </dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-xs uppercase tracking-wide text-text-muted">Content hash</dt>
                  <dd className="font-mono text-xs text-text-muted" title={bio?.content_hash}>
                    {bio?.content_hash ? shortHash(bio.content_hash) : "—"}
                  </dd>
                </div>
              </dl>
            );
          })()}
          {linkedinSync && (
            <div
              className={`mt-4 rounded-md border px-3 py-3 text-sm ${
                linkedinSync.ok
                  ? "border-accent/40 bg-accent-muted text-text-primary"
                  : "border-red-500/30 bg-red-500/10 text-red-300"
              }`}
            >
              {linkedinSync.ok && linkedinSync.result === "unchanged" && (
                <>
                  <p>Sync completed. No changes detected.</p>
                  <p className="mt-1 text-xs text-text-secondary">
                    Current version: {linkedinSync.new_version != null ? `v${linkedinSync.new_version}` : "—"}
                  </p>
                </>
              )}
              {linkedinSync.ok && linkedinSync.result === "updated" && (
                <>
                  <p>Bio updated.</p>
                  <p className="mt-1 text-xs text-text-secondary">
                    Previous version: v{linkedinSync.previous_version} → New version: v{linkedinSync.new_version}
                  </p>
                  {linkedinSync.change_summary && (
                    <p className="mt-1 text-xs text-text-secondary">Changes: {linkedinSync.change_summary}</p>
                  )}
                  <p className="mt-1 text-xs text-text-secondary">
                    {linkedinSync.agent_reloaded
                      ? "Agent knowledge reloaded successfully."
                      : "Knowledge file updated; agent reload was not confirmed."}
                  </p>
                </>
              )}
              {!linkedinSync.ok && (
                <>
                  <p>Sync failed. Current knowledge was kept.</p>
                  <p className="mt-1 text-xs text-red-200/90">{formatLinkedInSyncError(linkedinSync)}</p>
                </>
              )}
            </div>
          )}
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
    </div>
  );
}
