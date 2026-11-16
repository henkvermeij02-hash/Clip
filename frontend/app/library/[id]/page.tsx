"use client";

import { ArrowLeft, RefreshCw, Save, ShieldCheck, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { JobList } from "@/components/JobList";
import { Alert, Badge, Button, Card, Field, PageHeader, Spinner, StatusBadge, inputClass } from "@/components/ui";
import { API_URL, del, patch, post, type Video } from "@/lib/api";
import { formatBytes, formatDate, formatDuration, resolution } from "@/lib/format";
import { usePolling } from "@/lib/usePolling";

export default function VideoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: video, error, reload } = usePolling<Video>(`/api/videos/${id}`, 3000);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  if (error && !video) {
    return (
      <>
        <Link href="/library" className="mb-4 inline-flex items-center gap-1 text-sm text-zinc-400 hover:text-white"><ArrowLeft className="h-4 w-4" />Library</Link>
        <Alert>{error}</Alert>
      </>
    );
  }
  if (!video) return <Spinner />;

  async function reprocess() {
    setBusy("reprocess");
    setActionError(null);
    try {
      await post(`/api/videos/${id}/reprocess`);
      reload();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    const copied = video!.storage_mode === "copied";
    const question = copied
      ? "Remove this video from the library AND delete the app's copy of the file? Your original recording (if you still have it elsewhere) is not touched."
      : "Remove this video from the library? Your original file stays exactly where it is.";
    if (!window.confirm(question)) return;
    setBusy("delete");
    try {
      await del(`/api/videos/${id}?delete_file=${copied}`);
      router.push("/library");
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
      setBusy(null);
    }
  }

  const meta: [string, string][] = [
    ["Duration", formatDuration(video.duration_seconds)],
    ["Resolution", resolution(video.width, video.height)],
    ["Frame rate", video.fps ? `${video.fps} fps` : "–"],
    ["Video codec", video.video_codec ?? "–"],
    ["Audio", video.has_audio == null ? "–" : video.has_audio ? video.audio_codec ?? "yes" : "No audio track"],
    ["Bitrate", video.bitrate ? `${(video.bitrate / 1e6).toFixed(1)} Mbit/s` : "–"],
    ["File size", formatBytes(video.file_size)],
    ["Container", video.container?.split(",")[0] ?? "–"],
    ["Storage", video.storage_mode === "copied" ? "Copied into library" : "Kept in original location"],
    ["Imported", formatDate(video.created_at)],
  ];

  return (
    <>
      <Link href="/library" className="mb-4 inline-flex items-center gap-1 text-sm text-zinc-400 hover:text-white"><ArrowLeft className="h-4 w-4" />Library</Link>
      <PageHeader
        title={video.title || video.original_filename}
        description={<span className="flex flex-wrap items-center gap-2"><StatusBadge status={video.status} /><span className="break-all">{video.original_filename}</span></span>}
        actions={
          <>
            <Button onClick={reprocess} loading={busy === "reprocess"} disabled={!video.file_exists}><RefreshCw className="h-4 w-4" />Re-read metadata</Button>
            <Button variant="danger" onClick={remove} loading={busy === "delete"}><Trash2 className="h-4 w-4" />Remove</Button>
          </>
        }
      />
      <div className="space-y-4">
        {actionError && <Alert onClose={() => setActionError(null)}>{actionError}</Alert>}
        {!video.file_exists && <Alert>The video file is missing at <code className="break-all">{video.file_path}</code>. If you moved it, import it again from its new location.</Alert>}
        {video.status === "error" && video.error && <Alert>{video.error}</Alert>}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-5">
        <div className="min-w-0 space-y-6 lg:col-span-3">
          <div className="overflow-hidden rounded-2xl border border-ink-700 bg-black">
            {video.file_exists ? (
              <video key={video.id} controls preload="metadata" className="aspect-video w-full" src={`${API_URL}/api/videos/${video.id}/stream`}
                poster={video.has_thumbnail ? `${API_URL}/api/videos/${video.id}/thumbnail` : undefined} />
            ) : <div className="flex aspect-video items-center justify-center text-sm text-zinc-500">File not available</div>}
          </div>
          <p className="text-xs text-zinc-500">Some formats (e.g. MKV or HEVC) may not play in every browser. That does not affect processing.</p>

          <Card title="Video details" subtitle="Read from the file with FFprobe.">
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
              {meta.map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3 border-b border-ink-700 pb-2 text-sm">
                  <dt className="text-zinc-400">{k}</dt><dd className="text-right text-zinc-100">{v}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-3 break-all text-xs text-zinc-500">Location: {video.file_path}</div>
          </Card>

          <Card title="Processing history">
            {video.jobs && video.jobs.length ? <JobList jobs={video.jobs} onChange={reload} showVideo={false} /> : <p className="text-sm text-zinc-500">No jobs yet.</p>}
          </Card>
        </div>

        <div className="min-w-0 space-y-6 lg:col-span-2">
          <DetailsForm video={video} onSaved={reload} />
          <RightsForm video={video} onSaved={reload} />
        </div>
      </div>
    </>
  );
}

function DetailsForm({ video, onSaved }: { video: Video; onSaved: () => void }) {
  const [title, setTitle] = useState(video.title ?? "");
  const [notes, setNotes] = useState(video.notes ?? "");
  const [state, setState] = useState<{ busy: boolean; error?: string; saved?: boolean }>({ busy: false });
  useEffect(() => { setTitle(video.title ?? ""); setNotes(video.notes ?? ""); }, [video.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setState({ busy: true });
    try {
      await patch(`/api/videos/${video.id}`, { title, notes });
      setState({ busy: false, saved: true });
      onSaved();
    } catch (err) {
      setState({ busy: false, error: err instanceof Error ? err.message : String(err) });
    }
  }

  return (
    <Card title="Title & notes">
      <form onSubmit={save} className="space-y-4">
        <Field label="Title" htmlFor="title"><input id="title" className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} /></Field>
        <Field label="Notes" htmlFor="notes" help="E.g. what happens in this session, moments you remember."><textarea id="notes" className={inputClass} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        {state.error && <Alert>{state.error}</Alert>}
        <div className="flex items-center gap-3">
          <Button type="submit" loading={state.busy}><Save className="h-4 w-4" />Save</Button>
          {state.saved && <span className="text-sm text-emerald-400">Saved</span>}
        </div>
      </form>
    </Card>
  );
}

function RightsForm({ video, onSaved }: { video: Video; onSaved: () => void }) {
  const [source, setSource] = useState(video.rights_source);
  const [confirmed, setConfirmed] = useState(video.rights_confirmed);
  const [monetization, setMonetization] = useState(video.monetization_status);
  const [notes, setNotes] = useState(video.rights_notes ?? "");
  const [state, setState] = useState<{ busy: boolean; error?: string; saved?: boolean }>({ busy: false });
  useEffect(() => {
    setSource(video.rights_source); setConfirmed(video.rights_confirmed);
    setMonetization(video.monetization_status); setNotes(video.rights_notes ?? "");
  }, [video.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setState({ busy: true });
    try {
      await patch(`/api/videos/${video.id}`, { rights_source: source, rights_confirmed: confirmed, monetization_status: monetization, rights_notes: notes });
      setState({ busy: false, saved: true });
      onSaved();
    } catch (err) {
      setState({ busy: false, error: err instanceof Error ? err.message : String(err) });
    }
  }

  return (
    <Card title={<span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-brand-400" />Rights & permissions</span>}
      actions={video.rights_confirmed ? <Badge tone="emerald">Confirmed</Badge> : <Badge tone="amber">Not confirmed</Badge>}>
      <form onSubmit={save} className="space-y-4">
        <Field label="Where does this footage come from?" htmlFor="source">
          <select id="source" className={inputClass} value={source} onChange={(e) => setSource(e.target.value as Video["rights_source"])}>
            <option value="own_recording">I recorded it myself</option>
            <option value="licensed">Licensed / given permission by the owner</option>
            <option value="other">Other</option>
          </select>
        </Field>
        <Field label="Monetisation status" htmlFor="monetization" help="Check the game publisher's current video policy and YouTube's monetisation rules. Unknown is the honest default.">
          <select id="monetization" className={inputClass} value={monetization} onChange={(e) => setMonetization(e.target.value as Video["monetization_status"])}>
            <option value="unknown">Unknown — not checked yet</option>
            <option value="not_monetized">Will not be monetised</option>
            <option value="cleared">I checked: monetisation is allowed</option>
            <option value="not_allowed">Monetisation is not allowed</option>
          </select>
        </Field>
        <Field label="Notes" htmlFor="rnotes" help="E.g. link to the policy you checked and the date.">
          <textarea id="rnotes" className={inputClass} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </Field>
        <label className="flex items-start gap-2 text-sm text-zinc-300">
          <input type="checkbox" className="mt-0.5 h-4 w-4 accent-pink-500" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
          I confirm I have the right to use this footage in videos, and the information above is accurate.
        </label>
        {state.error && <Alert>{state.error}</Alert>}
        <div className="flex items-center gap-3">
          <Button type="submit" loading={state.busy}><Save className="h-4 w-4" />Save rights</Button>
          {state.saved && <span className="text-sm text-emerald-400">Saved</span>}
        </div>
      </form>
    </Card>
  );
}
