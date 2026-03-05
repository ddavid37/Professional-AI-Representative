"use client";

import { FormEvent, useState } from "react";
import { CheckCircle, Mail, MessageSquare, Send, User } from "lucide-react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type FormState = "idle" | "loading" | "success" | "error";

export default function ContactPage() {
  const [name, setName]       = useState("");
  const [email, setEmail]     = useState("");
  const [question, setQuestion] = useState("");
  const [status, setStatus]   = useState<FormState>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (status === "loading") return;

    setStatus("loading");
    setErrorMsg("");

    try {
      // We call the non-streaming /api/chat endpoint with a pre-formatted lead message.
      // The LangGraph agent will detect the intent and trigger the LeadCapture tool.
      const body = JSON.stringify({
        message: `Please capture this lead — Name: ${name}, Email: ${email}, Question/Message: ${question}`,
      });

      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });

      if (!res.ok) throw new Error(`Server responded with ${res.status}`);

      setStatus("success");
      setName("");
      setEmail("");
      setQuestion("");
    } catch (err) {
      setStatus("error");
      setErrorMsg(
        err instanceof Error ? err.message : "Something went wrong. Please try again."
      );
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-20">

      {/* Header */}
      <div className="mb-14">
        <h1 className="text-4xl font-bold text-text-primary mb-3">
          Get in <span className="text-accent">touch</span>
        </h1>
        <p className="text-text-secondary max-w-xl leading-relaxed">
          Have a question about my work, a collaboration opportunity, or
          something my AI rep couldn't answer? Leave your details and I'll
          get back to you personally.
        </p>
      </div>

      <div className="grid gap-12 lg:grid-cols-[1fr_2fr]">

        {/* ── Left: info cards ──────────────────────────── */}
        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-surface p-5">
            <Mail size={18} className="text-accent mb-3" strokeWidth={1.5} />
            <p className="text-sm font-medium text-text-primary mb-1">Email</p>
            <p className="text-xs text-text-secondary">
              Replies within 24 hours on business days.
            </p>
          </div>

          <div className="rounded-xl border border-border bg-surface p-5">
            <MessageSquare size={18} className="text-accent mb-3" strokeWidth={1.5} />
            <p className="text-sm font-medium text-text-primary mb-1">Prefer async?</p>
            <p className="text-xs text-text-secondary">
              Chat with my AI rep first —{" "}
              <Link href="/chat" className="text-accent hover:underline">
                start a conversation
              </Link>
              . It can answer most questions instantly.
            </p>
          </div>

          <div className="rounded-xl border border-border bg-surface p-5">
            <User size={18} className="text-accent mb-3" strokeWidth={1.5} />
            <p className="text-sm font-medium text-text-primary mb-1">Currently open to</p>
            <ul className="text-xs text-text-secondary space-y-1 list-disc list-inside">
              <li>Full-time ML / AI Engineering roles (Summer 2026)</li>
              <li>Research collaborations in Federated Learning</li>
              <li>Speaking engagements & technical writing</li>
            </ul>
          </div>
        </div>

        {/* ── Right: form ───────────────────────────────── */}
        <div>
          {status === "success" ? (
            <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-accent/30 bg-accent-muted p-12 text-center h-full">
              <CheckCircle size={40} className="text-accent" strokeWidth={1.5} />
              <h2 className="text-xl font-semibold text-text-primary">Message received!</h2>
              <p className="text-sm text-text-secondary max-w-sm">
                Daniel has been notified and will follow up with you at{" "}
                <span className="text-text-primary font-medium">{email || "your email"}</span>{" "}
                shortly.
              </p>
              <button
                onClick={() => setStatus("idle")}
                className="mt-2 text-xs text-accent hover:underline"
              >
                Send another message
              </button>
            </div>
          ) : (
            <form
              onSubmit={onSubmit}
              className="rounded-xl border border-border bg-surface p-8 space-y-5"
            >
              <h2 className="text-lg font-semibold text-text-primary mb-2">
                Leave a message
              </h2>

              {/* Name */}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-text-secondary">
                  Full name <span className="text-accent">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Smith"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-accent transition-colors"
                />
              </div>

              {/* Email */}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-text-secondary">
                  Email address <span className="text-accent">*</span>
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="jane@company.com"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-accent transition-colors"
                />
              </div>

              {/* Question / message */}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-text-secondary">
                  Your question or message <span className="text-accent">*</span>
                </label>
                <textarea
                  required
                  rows={5}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="What would you like to discuss with Daniel?"
                  className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-accent transition-colors"
                />
              </div>

              {/* Error */}
              {status === "error" && (
                <p className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">
                  {errorMsg}
                </p>
              )}

              <button
                type="submit"
                disabled={status === "loading"}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent py-2.5 text-sm font-semibold text-background transition-opacity hover:opacity-90 disabled:opacity-60"
              >
                {status === "loading" ? (
                  <>
                    <span className="h-4 w-4 rounded-full border-2 border-background border-t-transparent animate-spin" />
                    Sending…
                  </>
                ) : (
                  <>
                    <Send size={14} />
                    Send message
                  </>
                )}
              </button>

              <p className="text-center text-xs text-text-muted">
                Your details are only used to follow up on your inquiry.
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
