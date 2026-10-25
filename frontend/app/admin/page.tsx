"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, RefreshCw, Shield, XCircle } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_STORAGE_KEY = "admin_token";
const POLL_MS = 30_000;

type CheckResult = {
  status: "ok" | "error" | "not_configured";
  detail: string;
  latency_ms: number;
  [key: string]: unknown;
};

type HealthPayload = {
  checked_at: string;
  ok: boolean;
  checks: Record<string, CheckResult>;
};

const LABELS: Record<string, string> = {
  openai: "OpenAI model",
  tavily: "Tavily search",
  twilio: "Twilio WhatsApp",
  storage: "Lead storage",
};

// Extra non-secret fields the backend reports per check.
const EXTRA_FIELDS: Record<string, string> = {
  model: "Model",
  sandbox: "Sandbox sender",
  content_sid_set: "TWILIO_CONTENT_SID set",
  template: "Template",
  whatsapp_to: "Sends to",
  store: "Store",
};

function readStoredToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

function storeToken(token: string) {
  try {
    if (token) sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
    else sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Storage blocked; the token just will not survive a reload.
  }
}

// Chat history lives in the visitor's browser, so check that storage here.
function browserStorageCheck(): CheckResult {
  const started = performance.now();
  try {
    const key = "__admin_probe__";
    window.localStorage.setItem(key, "ok");
    const ok = window.localStorage.getItem(key) === "ok";
    window.localStorage.removeItem(key);
    return {
      status: ok ? "ok" : "error",
      detail: ok
        ? "localStorage can be written and read (chat history survives reloads)."
        : "localStorage read back the wrong value.",
      latency_ms: Math.round(performance.now() - started),
    };
  } catch {
    return {
      status: "error",
      detail: "localStorage is blocked in this browser; chat history will not persist.",
      latency_ms: Math.round(performance.now() - started),
    };
  }
}

function StatusIcon({ status }: { status: CheckResult["status"] }) {
  if (status === "ok") return <CheckCircle2 size={18} className="text-emerald-400" />;
  if (status === "not_configured") return <AlertCircle size={18} className="text-amber-400" />;
  return <XCircle size={18} className="text-red-400" />;
}

function CheckCard({ name, check }: { name: string; check: CheckResult }) {
  const border =
    check.status === "ok"
      ? "border-emerald-500/30"
      : check.status === "not_configured"
        ? "border-amber-500/30"
        : "border-red-500/30";
  const extras = Object.entries(EXTRA_FIELDS).filter(([key]) => key in check);
  return (
    <div className={`rounded-lg border ${border} bg-surface/60 px-4 py-4`}>
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <StatusIcon status={check.status} />
          <span className="text-sm font-medium text-text-primary">{LABELS[name] ?? name}</span>
        </div>
        <span className="text-xs text-text-muted">{check.latency_ms} ms</span>
      </div>
      <p className="text-sm leading-relaxed text-text-secondary">{check.detail}</p>
      {extras.length > 0 && (
        <dl className="mt-3 space-y-1 text-xs">
          {extras.map(([key, label]) => (
            <div key={key} className="flex justify-between gap-3">
              <dt className="text-text-muted">{label}</dt>
              <dd className="text-text-secondary">{String(check[key])}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [tokenInput, setTokenInput] = useState("");
  const [data, setData] = useState<HealthPayload | null>(null);
  const [browser, setBrowser] = useState<CheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [needsToken, setNeedsToken] = useState(false);
  const [loading, setLoading] = useState(false);

  const fetchHealth = useCallback(async (adminToken: string) => {
    setBrowser(browserStorageCheck());
    if (!adminToken) {
      setNeedsToken(true);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/health`, {
        headers: { "X-Admin-Token": adminToken },
        cache: "no-store",
      });
      if (res.status === 401) {
        setNeedsToken(true);
        setError("Invalid admin token.");
        setData(null);
        storeToken("");
        return;
      }
      if (res.status === 503) {
        throw new Error("Admin page is disabled: set ADMIN_TOKEN on the API project.");
      }
      if (!res.ok) throw new Error(`API returned ${res.status}`);
      setData((await res.json()) as HealthPayload);
      setError(null);
      setNeedsToken(false);
      storeToken(adminToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Health check failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const stored = readStoredToken();
    setToken(stored);
    void fetchHealth(stored);
  }, [fetchHealth]);

  useEffect(() => {
    if (!token || needsToken) return;
    const id = window.setInterval(() => void fetchHealth(token), POLL_MS);
    return () => window.clearInterval(id);
  }, [token, needsToken, fetchHealth]);

  const handleUnlock = (e: React.FormEvent) => {
    e.preventDefault();
    const next = tokenInput.trim();
    setToken(next);
    setError(null);
    void fetchHealth(next);
  };

  if (needsToken && !data) {
    return (
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center px-6 py-16">
        <div className="rounded-xl border border-border bg-surface p-8">
          <div className="mb-6 flex items-center gap-3">
            <Shield size={22} className="text-accent" />
            <h1 className="font-display text-2xl text-text-primary">Admin status</h1>
          </div>
          <p className="mb-6 text-sm leading-relaxed text-text-secondary">
            Enter the <code className="text-accent">ADMIN_TOKEN</code> from the API environment.
          </p>
          <form onSubmit={handleUnlock} className="space-y-4">
            <input
              type="password"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder="Admin token"
              className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm text-text-primary outline-none focus:border-accent/60"
              autoComplete="off"
            />
            {error && (
              <p className="flex items-center gap-2 text-sm text-red-400">
                <AlertCircle size={14} />
                {error}
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
    <div className="mx-auto w-full max-w-5xl px-6 py-10 lg:px-12">
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-text-primary">Admin status</h1>
          <p className="mt-2 text-sm text-text-secondary">
            Live connectivity checks, refreshed every 30 seconds.
            {data && ` Last checked ${new Date(data.checked_at).toLocaleTimeString()}.`}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void fetchHealth(token)}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-text-secondary transition-colors hover:border-accent/50 hover:text-text-primary disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-8 flex items-start gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {!data && !error ? (
        <div className="flex items-center gap-2 text-sm text-text-muted">
          <Loader2 size={14} className="animate-spin" />
          Running checks…
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {data &&
            Object.entries(data.checks).map(([name, check]) => (
              <CheckCard key={name} name={name} check={check} />
            ))}
          {browser && <CheckCard name="Chat history (this browser)" check={browser} />}
        </div>
      )}
    </div>
  );
}
