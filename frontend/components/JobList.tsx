"use client";

import { ChevronDown, RotateCcw, XCircle } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { post, type Job } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import { Button, ProgressBar, StatusBadge } from "./ui";

export function JobList({ jobs, onChange, showVideo = true }: { jobs: Job[]; onChange?: () => void; showVideo?: boolean }) {
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);

  async function act(job: Job, action: "retry" | "cancel") {
    setBusy(job.id);
    setError(null);
    try {
      await post(`/api/jobs/${job.id}/${action}`);
      onChange?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="divide-y divide-ink-700 overflow-hidden rounded-xl border border-ink-700">
      {error && <div className="bg-red-500/10 px-4 py-2 text-sm text-red-300">{error}</div>}
      {jobs.map((job) => (
        <div key={job.id} className="bg-ink-900 px-4 py-3">
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge status={job.status} />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-zinc-100">
                {job.label}
                {showVideo && job.video_id && (
                  <Link href={`/library/${job.video_id}`} className="ml-2 text-xs font-normal text-brand-400 hover:underline">video #{job.video_id}</Link>
                )}
              </div>
              <div className="truncate text-xs text-zinc-500">
                #{job.id} · {job.message || "–"} · attempt {job.attempts}/{job.max_attempts} · {timeAgo(job.updated_at)}
              </div>
            </div>
            <div className="flex gap-2">
              {(job.status === "failed" || job.status === "cancelled") && (
                <Button variant="secondary" className="px-3 py-1.5 text-xs" loading={busy === job.id} onClick={() => act(job, "retry")}>
                  <RotateCcw className="h-3.5 w-3.5" /> Retry
                </Button>
              )}
              {(job.status === "queued" || job.status === "running") && (
                <Button variant="ghost" className="px-3 py-1.5 text-xs" loading={busy === job.id} onClick={() => act(job, "cancel")}>
                  <XCircle className="h-3.5 w-3.5" /> Cancel
                </Button>
              )}
            </div>
          </div>
          {job.status === "running" && <ProgressBar value={job.progress} className="mt-2" />}
          {job.error && (
            <div className="mt-2 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-300">
              <div className="flex items-start justify-between gap-2">
                <span className="min-w-0 break-words">{job.error}</span>
                {job.error_detail && (
                  <button className="flex shrink-0 items-center gap-1 text-red-400 hover:text-red-200" onClick={() => setExpanded(expanded === job.id ? null : job.id)}>
                    Technical details <ChevronDown className="h-3 w-3" />
                  </button>
                )}
              </div>
              {expanded === job.id && <pre className="mt-2 max-h-60 overflow-auto whitespace-pre-wrap text-[11px] text-red-200/80">{job.error_detail}</pre>}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
