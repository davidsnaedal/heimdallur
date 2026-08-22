import React, { useEffect, useMemo, useState } from "react";

type Source = "lbl" | "domar";

type Hit = {
  source: Source;
  source_label: string;
  id: string;
  title: string;
  subtitle: string;
  date: string | null;
  year: string | null;
  preview: string;
  source_url: string | null;
  open_url: string | null;
  preview_kind: Source;
  meta: {
    errand_type?: string;
    filename?: string;
    issue_path?: string;
    court?: string;
    case_number?: string;
    title?: string;
    keywords?: string[];
    has_pdf?: boolean;
    verdict_date?: string | null;
  };
};

type SearchReport = {
  query: string;
  mode: string;
  kennitala: string | null;
  name: string | null;
  total: number;
  by_source: { lbl: number; domar: number };
  by_year: Record<string, number>;
  by_type: Record<string, number>;
  by_court: Record<string, number>;
  hits: Hit[];
  warnings: string[];
  summary: string;
};

type Health = {
  status: string;
  indexes: Record<string, { status?: string }>;
};

function clsx(...parts: Array<string | false | undefined>) {
  return parts.filter(Boolean).join(" ");
}

function renderHighlighted(text: string) {
  const parts: React.ReactNode[] = [];
  const start = "[[[";
  const stop = "]]]";
  let i = 0;
  while (i < text.length) {
    const s = text.indexOf(start, i);
    if (s === -1) {
      parts.push(text.slice(i));
      break;
    }
    if (s > i) parts.push(text.slice(i, s));
    const e = text.indexOf(stop, s + start.length);
    if (e === -1) {
      parts.push(text.slice(s));
      break;
    }
    const inner = text.slice(s + start.length, e);
    parts.push(
      <span
        key={`${s}-${e}`}
        className="rounded bg-rose-500/10 px-1 text-rose-300 ring-1 ring-rose-500/30"
      >
        {inner}
      </span>
    );
    i = e + stop.length;
  }
  return parts;
}

function resolveApiBase(): string {
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (raw && raw.trim() !== "") return raw.trim();
  if (typeof window !== "undefined") return window.location.origin;
  return "http://localhost:8003";
}

function previewSrc(hit: Hit): string {
  const origin =
    typeof window !== "undefined" ? window.location.origin : "http://localhost:5175";
  const url = new URL("/api/preview", origin);
  url.searchParams.set("source", hit.source);
  if (hit.source === "lbl" && hit.source_url) {
    url.searchParams.set("url", hit.source_url);
  }
  if (hit.source === "domar") {
    url.searchParams.set("id", hit.id);
  }
  return url.toString();
}

type IframeStatus = "loading" | "loaded" | "error";

function PdfPreviewModal({
  hit,
  open,
  onClose
}: {
  hit: Hit | null;
  open: boolean;
  onClose: () => void;
}) {
  const [status, setStatus] = useState<IframeStatus>("loading");

  useEffect(() => {
    if (!open || !hit) return;
    setStatus("loading");
  }, [open, hit?.id, hit?.source, hit?.source_url]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open || !hit) return null;

  const embedUrl = previewSrc(hit);
  const showFallback = status === "error";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Document preview"
    >
      <button
        type="button"
        aria-label="Close preview"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative w-full max-w-5xl overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl shadow-black/40">
        <div className="flex items-start justify-between gap-4 border-b border-slate-800 bg-slate-950/70 p-4">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-slate-100">
              {hit.title}
            </div>
            <div className="mt-0.5 truncate text-xs text-slate-400">
              {hit.source_label}
              {hit.subtitle ? ` · ${hit.subtitle}` : ""}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {hit.open_url ? (
              <a
                href={hit.open_url}
                target="_blank"
                rel="noreferrer"
                className="rounded-lg border border-slate-700 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-950 hover:bg-white"
              >
                Open source
              </a>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-900"
            >
              Close
            </button>
          </div>
        </div>
        <div className="relative h-[70vh] bg-slate-950">
          {status === "loading" ? (
            <div className="pointer-events-none absolute inset-x-0 top-3 z-10 flex justify-center">
              <div className="rounded-xl border border-slate-800 bg-slate-900/80 px-4 py-2 text-sm text-slate-200">
                Loading preview…
              </div>
            </div>
          ) : null}
          {showFallback ? (
            <div className="absolute inset-0 z-20 flex items-center justify-center p-6">
              <div className="max-w-lg rounded-2xl border border-slate-800 bg-slate-900/40 p-5 text-sm text-slate-200">
                Preview unavailable in-page. Use Open source instead.
              </div>
            </div>
          ) : null}
          <iframe
            key={embedUrl}
            title={`Preview: ${hit.title}`}
            src={embedUrl}
            className={clsx(
              "h-full w-full bg-slate-950",
              showFallback ? "hidden" : "block"
            )}
            onLoad={() => setStatus("loaded")}
            onError={() => setStatus("error")}
          />
        </div>
      </div>
    </div>
  );
}

function sourceBadge(source: Source) {
  if (source === "lbl") {
    return "border-amber-700/50 bg-amber-500/15 text-amber-100";
  }
  return "border-sky-700/50 bg-sky-500/15 text-sky-100";
}

export function App() {
  const apiBase = resolveApiBase();
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<SearchReport | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [sourceFilter, setSourceFilter] = useState<Source | null>(null);
  const [yearFilter, setYearFilter] = useState<string | null>(null);
  const [selected, setSelected] = useState<Hit | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  useEffect(() => {
    fetch(`${apiBase}/api/health`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setHealth(data))
      .catch(() => undefined);
  }, [apiBase]);

  const canSearch = q.trim().length >= 2;

  const filteredHits = useMemo(() => {
    if (!report) return [];
    return report.hits.filter((h) => {
      if (sourceFilter && h.source !== sourceFilter) return false;
      if (yearFilter && h.year !== yearFilter) return false;
      return true;
    });
  }, [report, sourceFilter, yearFilter]);

  async function runSearch() {
    if (!canSearch) return;
    setLoading(true);
    setError(null);
    setSourceFilter(null);
    setYearFilter(null);
    try {
      const url = new URL("/api/search", apiBase);
      url.searchParams.set("q", q.trim());
      url.searchParams.set("limit", "200");
      const res = await fetch(url.toString());
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const detail =
          (data && (data.detail as string)) || `Search failed: HTTP ${res.status}`;
        throw new Error(detail);
      }
      setReport(data as SearchReport);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
      setReport(null);
    } finally {
      setLoading(false);
    }
  }

  const indexLabel = health
    ? health.status === "ok"
      ? "LBL + Dómar online"
      : "One or more indexes unreachable"
    : "Checking indexes…";

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-5xl px-4 py-10">
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-2xl font-semibold tracking-tight">
                Heimdallur
              </div>
              <div className="text-sm text-slate-300">
                Exact person search across Lögbirtingablað and court judgments.
              </div>
            </div>
            <div className="rounded-full border border-slate-800 bg-slate-900/60 px-3 py-1 text-xs text-slate-300">
              {indexLabel}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 shadow-lg shadow-black/20">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") runSearch();
                }}
                placeholder='Full name or kennitala (e.g. "Jón Jónsson" or 010180-1234)'
                className="w-full flex-1 rounded-xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 outline-none ring-0 placeholder:text-slate-500 focus:border-sky-500/70 focus:ring-4 focus:ring-sky-500/10"
              />
              <button
                onClick={runSearch}
                disabled={!canSearch || loading}
                className={clsx(
                  "rounded-xl px-4 py-3 font-medium",
                  "border border-slate-700 bg-slate-50 text-slate-950",
                  "hover:bg-white active:translate-y-px",
                  (!canSearch || loading) &&
                    "cursor-not-allowed opacity-60 hover:bg-slate-50"
                )}
              >
                {loading ? "Searching..." : "Search"}
              </button>
            </div>
            {error ? (
              <div className="mt-3 rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
                {error}
              </div>
            ) : null}
            <div className="mt-3 text-xs text-slate-400">
              Only a full name (given name + surname) or a kennitala is accepted.
              Matches are exact phrases — no keyword search. Icelandic name cases
              (Jón / Jóns / Jóni) count as the same name.
            </div>
          </div>

          {report ? (
            <div className="mt-2 flex flex-col gap-3">
              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
                <div className="text-xs font-medium uppercase tracking-wide text-slate-400">
                  Overview for “{report.query}”
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-100">
                  {report.summary}
                </p>
                {report.warnings.length > 0 ? (
                  <div className="mt-3 rounded-xl border border-amber-800/70 bg-amber-950/40 px-4 py-3 text-sm text-amber-100">
                    One or more indexes failed, so this list may be incomplete.
                    <div className="mt-1 text-xs text-amber-200/90">
                      {report.warnings.join(" · ")}
                    </div>
                  </div>
                ) : null}
                <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                    <div className="text-xs text-slate-400">Total</div>
                    <div className="mt-1 text-2xl font-semibold text-slate-100">
                      {sourceFilter || yearFilter
                        ? `${filteredHits.length} / ${report.total}`
                        : report.total}
                    </div>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                    <div className="text-xs text-slate-400">By source</div>
                    <ul className="mt-2 space-y-1 text-sm text-slate-200">
                      {(
                        [
                          ["lbl", "Lögbirtingablað", report.by_source.lbl],
                          ["domar", "Dómar", report.by_source.domar]
                        ] as const
                      ).map(([key, label, n]) => (
                        <li key={key}>
                          <button
                            type="button"
                            onClick={() =>
                              setSourceFilter((cur) => (cur === key ? null : key))
                            }
                            className={clsx(
                              "flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1 text-left",
                              sourceFilter === key
                                ? "bg-sky-500/20 text-sky-100 ring-1 ring-sky-500/40"
                                : "hover:bg-slate-900/80"
                            )}
                          >
                            <span>{label}</span>
                            <span className="text-slate-400">{n}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                    <div className="flex items-center justify-between">
                      <div className="text-xs text-slate-400">By year</div>
                      {sourceFilter || yearFilter ? (
                        <button
                          type="button"
                          onClick={() => {
                            setSourceFilter(null);
                            setYearFilter(null);
                          }}
                          className="text-xs font-medium text-sky-300 hover:text-sky-200"
                        >
                          Clear
                        </button>
                      ) : null}
                    </div>
                    <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto text-sm text-slate-200">
                      {Object.entries(report.by_year).map(([k, n]) => (
                        <li key={k}>
                          <button
                            type="button"
                            onClick={() =>
                              setYearFilter((cur) => (cur === k ? null : k))
                            }
                            className={clsx(
                              "flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1 text-left",
                              yearFilter === k
                                ? "bg-sky-500/20 text-sky-100 ring-1 ring-sky-500/40"
                                : "hover:bg-slate-900/80"
                            )}
                          >
                            <span>{k}</span>
                            <span className="text-slate-400">{n}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>

              <div className="text-sm text-slate-300">
                Timeline:{" "}
                <span className="font-semibold text-slate-100">
                  {filteredHits.length}
                </span>
              </div>

              <div className="grid grid-cols-1 gap-3">
                {filteredHits.map((h) => (
                  <div
                    key={`${h.source}-${h.id}`}
                    role="button"
                    tabIndex={0}
                    onClick={() => {
                      setSelected(h);
                      setPreviewOpen(true);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelected(h);
                        setPreviewOpen(true);
                      }
                    }}
                    className={clsx(
                      "group cursor-pointer rounded-2xl border border-slate-800 bg-slate-900/30 p-4",
                      "hover:border-slate-700 hover:bg-slate-900/50",
                      "focus:outline-none focus:ring-4 focus:ring-sky-500/15"
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="truncate text-base font-semibold text-slate-100">
                        {h.title}
                        {h.date ? ` · ${h.date}` : ""}
                      </div>
                      <div
                        className={clsx(
                          "shrink-0 rounded-full border px-2 py-0.5 text-xs",
                          sourceBadge(h.source)
                        )}
                      >
                        {h.source_label}
                      </div>
                    </div>
                    {h.subtitle ? (
                      <div className="mt-1 text-xs text-slate-400 whitespace-pre-wrap">
                        {h.subtitle}
                      </div>
                    ) : null}
                    <div className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-200">
                      {h.preview ? renderHighlighted(h.preview) : "—"}
                    </div>
                  </div>
                ))}
                {filteredHits.length === 0 ? (
                  <div className="rounded-2xl border border-slate-800 bg-slate-900/20 p-6 text-sm text-slate-300">
                    {report.warnings.length > 0
                      ? "No results could be shown because an index timed out or failed. Retry the search."
                      : "No exact matches in the indexed sources."}
                  </div>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/20 p-6 text-sm text-slate-300">
              Search a person by full name or kennitala. Results from both
              indexes are merged into one timeline.
            </div>
          )}
        </div>
      </div>
      <PdfPreviewModal
        hit={selected}
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
      />
    </div>
  );
}
