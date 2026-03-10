"use client";

export default function ResumePage() {
  return (
    <main className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-5xl flex-col px-4 py-6 md:px-6">
      <header className="mb-4 border-b border-border pb-4">
        <h1 className="text-lg font-semibold text-text-primary">Daniel&apos;s Resume</h1>
        <p className="mt-1 text-xs text-text-secondary">
          View or download the latest version of Daniel&apos;s resume.
        </p>
      </header>

      <section className="flex-1 rounded-xl border border-border bg-surface/60 p-2">
        <iframe
          src="/api/resume"
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

