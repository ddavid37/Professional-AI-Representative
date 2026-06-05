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
  Search,
  Server,
  Shield,
} from "lucide-react";

const skills = [
  { icon: BrainCircuit, label: "LangGraph & Agentic AI",   desc: "Multi-agent orchestration, state machines, tool-calling loops." },
  { icon: Network,      label: "Federated Learning",       desc: "Privacy-preserving ML with NVFlare across distributed nodes." },
  { icon: Shield,       label: "ML Security",              desc: "Adversarial robustness, prompt injection guards, secure inference." },
  { icon: Server,       label: "FastAPI & Cloud",          desc: "Production Python backends with SSE streaming and serverless deploys." },
  { icon: Lock,         label: "LLM Ops",                  desc: "OpenAI & Azure Foundry, RAG pipelines, Pydantic-validated tool schemas." },
  { icon: Github,       label: "Open Source",              desc: "NVFlare contributor. Active GitHub presence in ML & AI infra repos." },
];

export default function HomePage() {
  return (
    <div className="w-full">

      {/* ── Hero — full viewport ──────────────────────────────── */}
      <section className="relative min-h-[calc(100vh-4rem)] w-full">
        <div className="grid h-full min-h-[calc(100vh-4rem)] w-full grid-cols-1 items-center gap-10 px-6 py-16 lg:grid-cols-[1fr_auto] lg:gap-16 lg:px-12 xl:px-20 xl:gap-24">
          {/* Left: text */}
          <div className="flex flex-col gap-7 lg:max-w-2xl">
            <span className="inline-flex w-fit items-center gap-2 rounded-full border border-border bg-surface/80 px-3.5 py-1.5 text-xs tracking-wide text-text-secondary">
              <Search size={12} className="text-accent" strokeWidth={2} />
              Open to full-time ML / AI roles
            </span>

            <h1 className="font-display text-[2.75rem] leading-[1.08] tracking-tight text-text-primary sm:text-6xl lg:text-7xl xl:text-[4.25rem]">
              Hi, I'm{" "}
              <span className="text-accent">Daniel David</span>
            </h1>

            <p className="max-w-xl text-lg leading-relaxed text-text-secondary lg:text-xl lg:leading-relaxed">
              Columbia University graduate{" "}
              <span className="text-text-primary">(B.A. Computer Science, May 2026)</span>.
              Former ML Engineer at Rhino Federated Computing. I build
              privacy-preserving AI systems, agentic workflows, and
              production-grade ML pipelines — and I'm looking for my next role.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Link
                href="/chat"
                className="inline-flex items-center gap-2 rounded-lg bg-accent px-6 py-3 text-sm font-medium text-background transition-opacity hover:opacity-90"
              >
                <MessageSquare size={15} />
                Chat with my AI Rep
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-lg border border-border px-6 py-3 text-sm text-text-secondary transition-colors hover:border-accent/50 hover:text-text-primary"
              >
                Get in touch
                <ArrowRight size={14} />
              </Link>
            </div>

            <div className="flex items-center gap-5 pt-2">
              <a
                href="http://github.com/ddavid37"
                target="_blank"
                rel="noreferrer noopener"
                className="text-text-muted transition-colors hover:text-text-primary"
                aria-label="GitHub"
              >
                <Github size={20} />
              </a>
              <a
                href="https://www.linkedin.com/in/ddavid37"
                target="_blank"
                rel="noreferrer noopener"
                className="text-text-muted transition-colors hover:text-text-primary"
                aria-label="LinkedIn"
              >
                <Linkedin size={20} />
              </a>
            </div>
          </div>

          {/* Right: photo */}
          <div className="mx-auto shrink-0 lg:mx-0 lg:mr-4 xl:mr-8">
            <div className="relative h-72 w-72 overflow-hidden rounded-2xl border border-border/80 shadow-2xl shadow-black/40 sm:h-80 sm:w-80 lg:h-[28rem] lg:w-[22rem] xl:h-[32rem] xl:w-[26rem]">
              <Image
                src="/DanielProfessionalPicture.png"
                alt="Daniel David"
                fill
                className="object-cover object-top"
                priority
              />
            </div>
          </div>
        </div>
      </section>

      {/* ── Status banner ───────────────────────────────────── */}
      <section className="w-full px-6 pb-24 lg:px-12 xl:px-20">
        <div className="flex w-full flex-col items-start gap-5 rounded-2xl border border-border bg-surface/60 p-8 md:flex-row md:items-center md:gap-8">
          <GraduationCap size={36} className="shrink-0 text-accent" strokeWidth={1.25} />
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-widest text-accent">
              Recently graduated
            </p>
            <h2 className="font-display text-2xl text-text-primary md:text-3xl">
              B.A. Computer Science — Columbia University
            </h2>
            <p className="mt-2 max-w-3xl text-base leading-relaxed text-text-secondary">
              Focused on AI/ML, distributed systems, and software engineering.
              Previously at Rhino Federated Computing. Now exploring full-time
              opportunities in ML engineering, applied AI, and federated learning.
            </p>
          </div>
        </div>
      </section>

      {/* ── Skills grid ───────────────────────────────────────── */}
      <section className="w-full px-6 pb-24 lg:px-12 xl:px-20">
        <h2 className="font-display mb-10 text-3xl text-text-primary md:text-4xl">
          What I work on
        </h2>
        <div className="grid w-full gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {skills.map(({ icon: Icon, label, desc }) => (
            <div
              key={label}
              className="group rounded-2xl border border-border bg-surface/40 p-6 transition-colors hover:border-accent/30 hover:bg-surface/70"
            >
              <Icon
                size={20}
                className="mb-4 text-accent opacity-90 transition-opacity group-hover:opacity-100"
                strokeWidth={1.25}
              />
              <h3 className="mb-2 text-sm font-medium text-text-primary">
                {label}
              </h3>
              <p className="text-sm leading-relaxed text-text-secondary">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ───────────────────────────────────────────────── */}
      <section className="w-full px-6 pb-24 lg:px-12 xl:px-20">
        <div className="w-full rounded-2xl border border-accent/20 bg-accent-muted px-8 py-14 text-center md:px-16">
          <h2 className="font-display mb-3 text-2xl text-text-primary md:text-3xl">
            Not sure what to ask?
          </h2>
          <p className="mx-auto mb-6 max-w-xl text-base text-text-secondary">
            My AI representative knows my background, projects, and skills.
            Ask it anything — if it doesn't know, it'll make sure I follow up.
          </p>
          <Link
            href="/chat"
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-6 py-3 text-sm font-medium text-background transition-opacity hover:opacity-90"
          >
            <MessageSquare size={14} />
            Start a conversation
          </Link>
        </div>
      </section>

    </div>
  );
}
