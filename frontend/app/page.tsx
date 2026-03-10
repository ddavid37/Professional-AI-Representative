import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  BrainCircuit,
  Github,
  GraduationCap,
  Linkedin,
  Lock,
  MessageSquare,
  Network,
  Server,
  Shield,
} from "lucide-react";

const skills = [
  { icon: BrainCircuit, label: "LangGraph & Agentic AI",   desc: "Multi-agent orchestration, state machines, tool-calling loops." },
  { icon: Network,      label: "Federated Learning",       desc: "Privacy-preserving ML with NVFlare across distributed nodes." },
  { icon: Shield,       label: "ML Security",              desc: "Adversarial robustness, prompt injection guards, secure inference." },
  { icon: Server,       label: "FastAPI & Cloud",          desc: "Production Python backends on Azure & Railway with SSE streaming." },
  { icon: Lock,         label: "LLM Ops",                  desc: "Azure OpenAI Foundry, RAG pipelines, Pydantic-validated tool schemas." },
  { icon: Github,       label: "Open Source",              desc: "NVFlare contributor. Active GitHub presence in ML & AI infra repos." },
];

export default function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-20">

      {/* ── Hero ───────────────────────────────────────────────── */}
      <section className="mb-28 flex flex-col-reverse items-start gap-10 md:flex-row md:items-center md:justify-between">
        {/* Left: text */}
        <div className="flex flex-col gap-6">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs text-text-secondary">
            <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
            Available · Graduating May 2026
          </span>

          <h1 className="text-5xl font-bold leading-tight tracking-tight md:text-6xl">
            Hi, I'm{" "}
            <span className="text-accent glow-accent">Daniel David</span>
          </h1>

          <p className="max-w-xl text-lg text-text-secondary leading-relaxed">
            ML Engineer at{" "}
            <span className="text-text-primary font-medium">Rhino Federated Computing</span>{" "}
            and CS student at{" "}
            <span className="text-text-primary font-medium">Columbia University</span>{" "}
            (Class of&nbsp;May&nbsp;2026). I build privacy-preserving AI systems,
            agentic workflows, and production-grade ML pipelines.
          </p>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/chat"
              className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-background transition-opacity hover:opacity-90"
            >
              <MessageSquare size={15} />
              Chat with my AI Rep
            </Link>
            <Link
              href="/contact"
              className="inline-flex items-center gap-2 rounded-lg border border-border px-5 py-2.5 text-sm text-text-secondary transition-colors hover:border-accent hover:text-accent"
            >
              Get in touch
              <ArrowRight size={14} />
            </Link>
          </div>

          {/* Social links */}
          <div className="flex items-center gap-4 pt-2">
            <a
              href="http://github.com/ddavid37"
              target="_blank"
              rel="noreferrer noopener"
              className="text-text-muted hover:text-text-primary transition-colors"
              aria-label="GitHub"
            >
              <Github size={18} />
            </a>
            <a
              href="https://www.linkedin.com/in/ddavid37"
              target="_blank"
              rel="noreferrer noopener"
              className="text-text-muted hover:text-text-primary transition-colors"
              aria-label="LinkedIn"
            >
              <Linkedin size={18} />
            </a>
          </div>
        </div>

        {/* Right: photo */}
        <div className="shrink-0">
          <div className="relative h-52 w-52 md:h-64 md:w-64 overflow-hidden rounded-2xl border border-border shadow-lg shadow-accent/10">
            <Image
              src="/DanielProfessionalPicture.png"
              alt="Daniel David"
              fill
              className="object-cover object-top"
              priority
            />
          </div>
        </div>
      </section>

      {/* ── Graduation banner ─────────────────────────────────── */}
      <section className="mb-28">
        <div className="rounded-xl border border-border bg-surface p-6 flex flex-col md:flex-row items-start md:items-center gap-4">
          <GraduationCap size={32} className="text-accent shrink-0" strokeWidth={1.5} />
          <div>
            <p className="text-sm font-medium text-accent mb-0.5">Upcoming milestone</p>
            <h2 className="text-lg font-semibold text-text-primary">
              B.S. Computer Science — Columbia University · May 2026
            </h2>
            <p className="text-sm text-text-secondary mt-1">
              Specialising in AI/ML, distributed systems, and software engineering.
              Open to full-time opportunities starting Summer 2026.
            </p>
          </div>
        </div>
      </section>

      {/* ── Skills grid ───────────────────────────────────────── */}
      <section className="mb-20">
        <h2 className="mb-8 text-2xl font-bold text-text-primary">
          What I work on
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {skills.map(({ icon: Icon, label, desc }) => (
            <div
              key={label}
              className="group rounded-xl border border-border bg-surface p-5 transition-colors hover:border-accent/40"
            >
              <Icon
                size={20}
                className="mb-3 text-accent opacity-80 group-hover:opacity-100 transition-opacity"
                strokeWidth={1.5}
              />
              <h3 className="text-sm font-semibold text-text-primary mb-1">
                {label}
              </h3>
              <p className="text-xs text-text-secondary leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ───────────────────────────────────────────────── */}
      <section className="rounded-xl border border-accent/20 bg-accent-muted p-8 text-center">
        <h2 className="text-xl font-bold mb-2 text-text-primary">
          Not sure what to ask?
        </h2>
        <p className="text-text-secondary text-sm mb-5 max-w-lg mx-auto">
          My AI representative knows my background, projects, and skills.
          Ask it anything — if it doesn't know, it'll make sure I follow up.
        </p>
        <Link
          href="/chat"
          className="inline-flex items-center gap-2 rounded-lg bg-accent px-6 py-2.5 text-sm font-semibold text-background hover:opacity-90 transition-opacity"
        >
          <MessageSquare size={14} />
          Start a conversation
        </Link>
      </section>

    </div>
  );
}
