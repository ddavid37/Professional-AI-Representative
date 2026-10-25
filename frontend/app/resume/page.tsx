"use client";

import { Download } from "lucide-react";

export default function ResumePage() {
  return (
    <main className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-5xl flex-col px-4 py-6 md:px-6">
      <header className="mb-4 flex flex-wrap items-end justify-between gap-3 border-b border-border pb-4">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Daniel&apos;s Resume</h1>
          <p className="mt-1 text-xs text-text-secondary">
            View or download the latest version of Daniel&apos;s resume.
          </p>
        </div>
        <a
          href="/api/resume"
          download="Daniel_David_CV.pdf"
          className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent/50 hover:text-text-primary"
        >
          <Download size={14} />
          Download PDF
        </a>
      </header>

      <section className="flex-1 rounded-xl border border-border bg-surface/60 p-2">
        <iframe
          src="/api/resume"
          title="Daniel David's resume"
          className="h-[70vh] w-full rounded-lg border border-border/60 bg-background"
        />
      </section>

      <p className="mt-3 text-xs text-text-secondary">
        If the embedded viewer doesn&apos;t load,{" "}
        <a
          href="/api/resume"
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent underline underline-offset-2"
        >
          open the PDF in a new tab
        </a>
        .
      </p>
    </main>
  );
}

