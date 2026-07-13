import { createFileRoute } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { ArrowUpRight, Cloud, CornerDownLeft, Loader2, Search, Sparkles } from "lucide-react";

const API_URL = "http://localhost:8000/query";

type Citation = {
  number: number;
  title: string;
  section?: string;
  url: string;
};

const EXAMPLES = [
  "How long did the route leak incident last?",
  "What caused the June 2022 outage?",
  "Which regions were affected by the WARP incident?",
];

export const Route = createFileRoute("/")({
  component: Index,
});

function Index() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setError("");
    setAnswer("");
    setCitations([]);
    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok) throw new Error(`Status ${res.status}`);
      const data = await res.json();
      setAnswer(data.answer);
      setCitations(data.citations ?? []);
    } catch (err) {
      console.error(err);
      setError("Couldn't reach the server. Is the backend running on :8000?");
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    submit(question);
  }

  return (
    <div className="relative min-h-screen bg-background text-foreground">
      {/* Ambient background */}
      <div className="pointer-events-none absolute inset-0 grid-pattern opacity-60" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[520px] bg-gradient-glow" />

      <div className="relative mx-auto max-w-3xl px-6 pb-24 pt-10 sm:pt-16">
        {/* Nav */}
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-primary shadow-glow">
              <Cloud className="h-4 w-4 text-primary-foreground" strokeWidth={2.5} />
            </div>
            <span className="text-sm font-semibold tracking-tight">Postmortem Q&A</span>
          </div>
          <a
            href="https://www.cloudflarestatus.com/history"
            target="_blank"
            rel="noopener noreferrer"
            className="group inline-flex items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            Incident history
            <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </a>
        </header>

        {/* Hero */}
        <section className="mt-20 text-center sm:mt-28">
          <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-border bg-surface/60 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            Grounded in Cloudflare's public postmortems
          </div>
          <h1 className="mt-6 font-display text-5xl leading-[1.05] tracking-tight sm:text-6xl">
             Cloudflare{" "}
            <em className="text-primary">incident assistant.</em>
          </h1>
          <p className="mx-auto mt-4 max-w-lg text-base text-muted-foreground">
            Natural-language search across every published Cloudflare postmortem. Every answer is
            sourced, timestamped, and linked back to the original writeup.
          </p>
        </section>

        {/* Search */}
        <form onSubmit={onSubmit} className="mt-10">
          <div className="group relative flex items-center gap-2 rounded-2xl border border-border-strong bg-surface p-2 shadow-card transition-all focus-within:border-primary focus-within:shadow-glow">
            <div className="grid h-10 w-10 shrink-0 place-items-center text-muted-foreground">
              <Search className="h-4 w-4" />
            </div>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask about any incident, cause, or recovery..."
              disabled={loading}
              className="min-w-0 flex-1 bg-transparent py-2 text-[15px] text-foreground placeholder:text-muted-foreground/70 focus:outline-none disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-gradient-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-glow transition-all hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-none disabled:bg-muted disabled:text-muted-foreground disabled:shadow-none"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Searching
                </>
              ) : (
                <>
                  Ask
                  <CornerDownLeft className="h-3.5 w-3.5" />
                </>
              )}
            </button>
          </div>

          {/* Examples */}
          {!answer && !loading && !error && (
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="py-1.5 text-xs text-muted-foreground">Try:</span>
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => {
                    setQuestion(ex);
                    submit(ex);
                  }}
                  className="rounded-full border border-border bg-surface/60 px-3 py-1.5 text-xs text-muted-foreground transition-all hover:border-border-strong hover:bg-surface hover:text-foreground"
                >
                  {ex}
                </button>
              ))}
            </div>
          )}
        </form>

        {/* Error */}
        {error && (
          <div className="mt-6 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive-foreground">
            <span className="font-medium text-destructive">Connection error · </span>
            <span className="text-muted-foreground">{error}</span>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="mt-8 space-y-3">
            <SkeletonBar className="w-24" />
            <div className="rounded-2xl border border-border bg-surface p-6 shadow-card">
              <SkeletonBar className="w-full" />
              <SkeletonBar className="mt-3 w-[92%]" />
              <SkeletonBar className="mt-3 w-[78%]" />
              <SkeletonBar className="mt-3 w-[60%]" />
            </div>
          </div>
        )}

        {/* Result */}
        {answer && !loading && (
          <div className="mt-10 space-y-6">
            <article className="rounded-2xl border border-border bg-gradient-surface p-6 shadow-card sm:p-8">
              <div className="mb-4 flex items-center gap-2">
                <div className="h-1.5 w-1.5 rounded-full bg-primary shadow-glow" />
                <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
                  Answer
                </h2>
              </div>
              <p className="whitespace-pre-wrap text-[15px] leading-[1.75] text-foreground">
                {answer}
              </p>
            </article>

            {citations.length > 0 && (
              <section>
                <h2 className="mb-3 px-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  Sources · {citations.length}
                </h2>
                <ul className="space-y-2">
                  {citations.map((c) => (
                    <li key={c.number}>
                      <a
                        href={c.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group flex gap-4 rounded-xl border border-border bg-surface p-4 transition-all hover:border-border-strong hover:bg-surface-elevated"
                      >
                        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-md border border-border bg-background font-mono text-xs font-semibold text-primary">
                          {c.number}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-start justify-between gap-3">
                            <h3 className="truncate text-sm font-semibold text-foreground">
                              {c.title}
                            </h3>
                            <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-primary" />
                          </div>
                          {c.section && (
                            <p className="mt-0.5 truncate text-xs text-muted-foreground">
                              {c.section}
                            </p>
                          )}
                          <p className="mt-1.5 truncate font-mono text-[11px] text-muted-foreground/70">
                            {c.url}
                          </p>
                        </div>
                      </a>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}

        <footer className="mt-24 border-t border-border pt-6 text-center text-xs text-muted-foreground">
          Not affiliated with Cloudflare. Answers generated from public postmortems.
        </footer>
      </div>
    </div>
  );
}

function SkeletonBar({ className = "" }: { className?: string }) {
  return <div className={`h-3 animate-pulse rounded-full bg-muted ${className}`} />;
}
