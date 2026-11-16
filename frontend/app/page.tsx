"use client";

import { CheckCircle2, CircleDashed, Clock, Film, HardDrive, ListChecks, Upload, XCircle } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { BackendDown } from "@/components/BackendDown";
import { JobList } from "@/components/JobList";
import { Card, EmptyState, PageHeader, Spinner, cx } from "@/components/ui";
import { VideoCard } from "@/components/VideoCard";
import type { Job, Stats, SystemStatus, Video } from "@/lib/api";
import { formatBytes, formatTotal } from "@/lib/format";
import { usePolling } from "@/lib/usePolling";

const PIPELINE: { step: string; phase: number }[] = [
  { step: "Import your gameplay recordings", phase: 1 },
  { step: "Find funny & crazy moments", phase: 2 },
  { step: "Suggest Shorts clips", phase: 2 },
  { step: "Write original voiceover scripts", phase: 3 },
  { step: "Generate local AI narration", phase: 3 },
  { step: "Edit into vertical 9:16 Shorts", phase: 4 },
  { step: "Subtitles, voice, branding", phase: 4 },
  { step: "Preview & approve every video", phase: 5 },
  { step: "Upload to YouTube (after approval)", phase: 5 },
  { step: "Learn from performance data", phase: 6 },
];
const CURRENT_PHASE = 1;

function Stat({ icon, label, value, hint }: { icon: ReactNode; label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-ink-700 bg-ink-900 p-5">
      <div className="flex items-center gap-2 text-sm text-zinc-400">{icon}{label}</div>
      <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
      {hint && <div className="mt-1 text-xs text-zinc-500">{hint}</div>}
    </div>
  );
}

function Check({ ok, optional, label, detail }: { ok: boolean; optional?: boolean; label: string; detail: ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-2.5">
      {ok ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" /> : optional ? <CircleDashed className="mt-0.5 h-5 w-5 shrink-0 text-zinc-500" /> : <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />}
      <div className="min-w-0">
        <div className="text-sm font-medium text-zinc-100">{label}{optional && !ok && <span className="ml-2 text-xs font-normal text-zinc-500">optional for now</span>}</div>
        <div className="break-words text-xs text-zinc-500">{detail}</div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const stats = usePolling<Stats>("/api/stats", 4000);
  const system = usePolling<SystemStatus>("/api/system/status", 15000);
  const videos = usePolling<Video[]>("/api/videos?limit=8", 4000);
  const active = usePolling<Job[]>("/api/jobs?status=queued,running,failed&limit=8", 2500);

  const s = stats.data;
  const sys = system.data;
  const backendError = stats.error && !s ? stats.error : null;

  return (
    <>
      <PageHeader
        title="Studio dashboard"
        description="Your footage, background processing and setup at a glance."
        actions={<Link href="/import" className="brand-gradient inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-white shadow-lg shadow-brand-500/20 hover:brightness-110"><Upload className="h-4 w-4" />Import footage</Link>}
      />
      {backendError && <div className="mb-6"><BackendDown error={backendError} /></div>}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat icon={<Film className="h-4 w-4" />} label="Recordings" value={s?.videos.total ?? "–"} hint={s ? `${s.videos.ready} ready · ${s.videos.processing} processing` : undefined} />
        <Stat icon={<Clock className="h-4 w-4" />} label="Footage" value={s ? formatTotal(s.videos.total_seconds) : "–"} hint="total length of ready videos" />
        <Stat icon={<ListChecks className="h-4 w-4" />} label="Jobs active" value={s ? s.jobs.running + s.jobs.queued : "–"} hint={s ? `${s.jobs.running} running · ${s.jobs.queued} queued` : undefined} />
        <Stat icon={<HardDrive className="h-4 w-4" />} label="Free disk space" value={sys ? formatBytes(sys.disk.free_bytes) : "–"} hint={s ? `library uses ${formatBytes(s.videos.library_bytes)}` : undefined} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="min-w-0 space-y-6 lg:col-span-2">
          <Card title="Recent recordings" actions={<Link href="/library" className="text-sm text-brand-400 hover:underline">View all</Link>}>
            {videos.loading && !videos.data ? <Spinner /> : videos.data && videos.data.length > 0 ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {videos.data.map((v) => <VideoCard key={v.id} video={v} />)}
              </div>
            ) : (
              <EmptyState icon={<Film className="h-8 w-8" />} title="No recordings yet">
                <Link href="/import" className="text-brand-400 hover:underline">Import your first GTA gameplay recording</Link> to get started.
              </EmptyState>
            )}
          </Card>

          <Card title="Background jobs" subtitle="Queued, running and failed work." actions={<Link href="/jobs" className="text-sm text-brand-400 hover:underline">All jobs</Link>}>
            {active.data && active.data.length > 0 ? <JobList jobs={active.data} onChange={active.reload} /> : (
              <p className="text-sm text-zinc-500">Nothing is running right now.</p>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="Setup check" subtitle="What this computer has ready.">
            {!sys ? <Spinner label="Checking…" /> : (
              <div className="divide-y divide-ink-700">
                <Check ok={sys.ffmpeg.available} label="FFmpeg" detail={sys.ffmpeg.available ? sys.ffmpeg.version : sys.ffmpeg.error} />
                <Check ok={sys.ffprobe.available} label="FFprobe" detail={sys.ffprobe.available ? "Reads video metadata" : sys.ffprobe.error} />
                <Check ok={sys.worker_running} label="Background worker" detail={sys.worker_running ? "Processing jobs" : "Not running — restart the backend."} />
                <Check ok={sys.ollama.available} optional label="Ollama (local AI)" detail={sys.ollama.available ? `${sys.ollama.models.length} model(s) installed` : "Needed from Phase 2. Install from ollama.com (free)."} />
              </div>
            )}
          </Card>

          <Card title="Production pipeline" subtitle={`Phase ${CURRENT_PHASE} of 6 is built.`}>
            <ol className="space-y-2.5">
              {PIPELINE.map(({ step, phase }) => {
                const done = phase <= CURRENT_PHASE;
                return (
                  <li key={step} className="flex items-center gap-3 text-sm">
                    <span className={cx("flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold", done ? "brand-gradient text-white" : "bg-ink-800 text-zinc-500")}>{done ? "✓" : phase}</span>
                    <span className={done ? "text-zinc-100" : "text-zinc-500"}>{step}</span>
                  </li>
                );
              })}
            </ol>
          </Card>
        </div>
      </div>
    </>
  );
}
