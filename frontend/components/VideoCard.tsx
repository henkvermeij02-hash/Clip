"use client";

import { AlertTriangle, Film, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { API_URL, type Video } from "@/lib/api";
import { formatBytes, formatDuration } from "@/lib/format";
import { StatusBadge } from "./ui";

export function VideoCard({ video }: { video: Video }) {
  return (
    <Link href={`/library/${video.id}`} className="group overflow-hidden rounded-2xl border border-ink-700 bg-ink-900 transition hover:border-ink-600 hover:bg-ink-850">
      <div className="relative aspect-video bg-ink-800">
        {video.has_thumbnail ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={`${API_URL}/api/videos/${video.id}/thumbnail?v=${encodeURIComponent(video.updated_at)}`} alt="" className="h-full w-full object-cover transition group-hover:scale-[1.02]" loading="lazy" />
        ) : (
          <div className="flex h-full items-center justify-center text-zinc-600"><Film className="h-8 w-8" /></div>
        )}
        <div className="absolute left-2 top-2 rounded-full bg-black/75 backdrop-blur-sm"><StatusBadge status={video.status} /></div>
        {video.duration_seconds != null && (
          <div className="absolute bottom-2 right-2 rounded-md bg-black/70 px-1.5 py-0.5 text-xs font-medium text-white">{formatDuration(video.duration_seconds)}</div>
        )}
      </div>
      <div className="space-y-1.5 p-3">
        <div className="truncate text-sm font-medium text-zinc-100" title={video.title || video.original_filename}>{video.title || video.original_filename}</div>
        <div className="flex items-center justify-between text-xs text-zinc-500">
          <span>{video.height ? `${video.height}p` : "–"}{video.fps ? ` · ${Math.round(video.fps)} fps` : ""} · {formatBytes(video.file_size)}</span>
          {video.rights_confirmed ? (
            <span className="flex items-center gap-1 text-emerald-400" title="Rights confirmed"><ShieldCheck className="h-3.5 w-3.5" /></span>
          ) : (
            <span className="flex items-center gap-1 text-amber-400" title="Rights not confirmed yet"><AlertTriangle className="h-3.5 w-3.5" /></span>
          )}
        </div>
        {video.status === "error" && video.error && <p className="line-clamp-2 text-xs text-red-300">{video.error}</p>}
      </div>
    </Link>
  );
}
