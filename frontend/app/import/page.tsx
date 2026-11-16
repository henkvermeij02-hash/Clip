"use client";

import { CheckCircle2, Copy, FileVideo, FolderOpen, Link2, Loader2, UploadCloud, XCircle } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { Alert, Button, Card, Field, PageHeader, ProgressBar, cx, inputClass } from "@/components/ui";
import { post, uploadFile, type FolderImportResult, type ImportResult } from "@/lib/api";
import { formatBytes } from "@/lib/format";

const ACCEPT = [".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".ts"];

interface UploadItem {
  key: string;
  file: File;
  progress: number;
  state: "waiting" | "uploading" | "done" | "duplicate" | "error";
  message?: string;
  videoId?: number;
  abort?: () => void;
}

export default function ImportPage() {
  return (
    <>
      <PageHeader
        title="Import footage"
        description="Add your own GTA gameplay recordings. After import the app reads each video's details (length, resolution, frame rate) in the background."
      />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <UploadCard />
        <PathImportCard />
      </div>
      <div className="mt-6">
        <Alert tone="warning">
          <strong>About rights:</strong> owning a recording does not automatically give you the right to monetise it. Game
          publishers set their own rules for gameplay videos. After importing, open each video and record its rights status — see{" "}
          <Link href="/rights" className="underline">Rights &amp; licences</Link>.
        </Alert>
      </div>
    </>
  );
}

function UploadCard() {
  const [items, setItems] = useState<UploadItem[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const runningRef = useRef(false);
  const queueRef = useRef<UploadItem[]>([]);

  const update = (key: string, patch: Partial<UploadItem>) =>
    setItems((prev) => prev.map((it) => (it.key === key ? { ...it, ...patch } : it)));

  async function processQueue() {
    if (runningRef.current) return;
    runningRef.current = true;
    // Upload one file at a time so the disk is not overloaded.
    while (queueRef.current.length) {
      const item = queueRef.current.shift()!;
      const { promise, abort } = uploadFile(item.file, (p) => update(item.key, { progress: p }));
      update(item.key, { state: "uploading", abort });
      try {
        const result = await promise;
        update(item.key, {
          state: result.status === "duplicate" ? "duplicate" : "done",
          progress: 1,
          message: result.message,
          videoId: result.video?.id,
          abort: undefined,
        });
      } catch (e) {
        update(item.key, { state: "error", message: e instanceof Error ? e.message : String(e), abort: undefined });
      }
    }
    runningRef.current = false;
  }

  function addFiles(list: FileList | File[]) {
    const files = Array.from(list);
    const newItems: UploadItem[] = files.map((file) => {
      const ok = ACCEPT.some((ext) => file.name.toLowerCase().endsWith(ext));
      return {
        key: `${file.name}-${file.size}-${file.lastModified}-${Math.random()}`,
        file,
        progress: 0,
        state: ok ? "waiting" : "error",
        message: ok ? undefined : `Not a supported video type (${ACCEPT.join(", ")}).`,
      };
    });
    setItems((prev) => [...newItems, ...prev]);
    queueRef.current.push(...newItems.filter((i) => i.state === "waiting"));
    processQueue();
  }

  return (
    <Card title="Upload from this browser" subtitle="Drag files in, or pick them. The file is copied into your library folder.">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files); }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        className={cx(
          "flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-12 text-center transition",
          dragging ? "border-brand-500 bg-brand-500/10" : "border-ink-600 hover:border-ink-600 hover:bg-ink-850",
        )}
      >
        <UploadCloud className={cx("h-10 w-10", dragging ? "text-brand-400" : "text-zinc-500")} />
        <p className="mt-3 font-medium text-zinc-100">Drop gameplay videos here</p>
        <p className="mt-1 text-sm text-zinc-500">or click to choose · MP4, MOV, MKV, WEBM, AVI · any size</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT.join(",") + ",video/*"}
          multiple
          className="hidden"
          onChange={(e) => { if (e.target.files?.length) addFiles(e.target.files); e.target.value = ""; }}
        />
      </div>

      {items.length > 0 && (
        <ul className="mt-4 space-y-2">
          {items.map((it) => (
            <li key={it.key} className="rounded-xl border border-ink-700 bg-ink-850 px-3 py-2.5">
              <div className="flex items-center gap-3">
                {it.state === "done" ? <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  : it.state === "duplicate" ? <Copy className="h-4 w-4 text-amber-400" />
                  : it.state === "error" ? <XCircle className="h-4 w-4 text-red-400" />
                  : it.state === "uploading" ? <Loader2 className="h-4 w-4 animate-spin text-sky-400" />
                  : <FileVideo className="h-4 w-4 text-zinc-500" />}
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm text-zinc-100">{it.file.name}</div>
                  <div className={cx("text-xs", it.state === "error" ? "text-red-300" : it.state === "duplicate" ? "text-amber-300" : "text-zinc-500")}>
                    {formatBytes(it.file.size)} ·{" "}
                    {it.state === "uploading" ? `Uploading ${Math.round(it.progress * 100)}%`
                      : it.state === "waiting" ? "Waiting…"
                      : it.message}
                  </div>
                </div>
                {it.videoId && <Link href={`/library/${it.videoId}`} className="text-xs text-brand-400 hover:underline">Open</Link>}
                {it.state === "uploading" && it.abort && (
                  <button className="text-xs text-zinc-400 hover:text-white" onClick={it.abort}>Cancel</button>
                )}
              </div>
              {it.state === "uploading" && <ProgressBar value={it.progress} className="mt-2" />}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function PathImportCard() {
  const [kind, setKind] = useState<"file" | "folder">("folder");
  const [path, setPath] = useState("");
  const [mode, setMode] = useState<"reference" | "copy">("reference");
  const [recursive, setRecursive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [single, setSingle] = useState<ImportResult | null>(null);
  const [folder, setFolder] = useState<FolderImportResult | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSingle(null);
    setFolder(null);
    try {
      if (kind === "file") setSingle(await post<ImportResult>("/api/videos/import-path", { path, mode }));
      else setFolder(await post<FolderImportResult>("/api/videos/import-folder", { path, mode, recursive }));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Import from a folder on this computer" subtitle="Best for large recordings — no browser upload needed.">
      <form onSubmit={submit} className="space-y-4">
        <div className="inline-flex rounded-xl border border-ink-600 bg-ink-850 p-1 text-sm">
          {(["folder", "file"] as const).map((k) => (
            <button type="button" key={k} onClick={() => setKind(k)} className={cx("rounded-lg px-3 py-1.5 font-medium transition", kind === k ? "bg-ink-700 text-white" : "text-zinc-400 hover:text-zinc-200")}>
              {k === "folder" ? "Whole folder" : "Single file"}
            </button>
          ))}
        </div>

        <Field
          label={kind === "folder" ? "Folder path" : "File path"}
          htmlFor="path"
          help={kind === "folder"
            ? <>Example: <code>C:\Users\you\Videos\GTA6</code> or <code>/Users/you/Movies/GTA6</code>. Tip: in Windows Explorer, right-click the folder → “Copy as path”.</>
            : <>Example: <code>D:\Captures\gta6_session.mp4</code></>}
        >
          <input id="path" className={inputClass} value={path} onChange={(e) => setPath(e.target.value)} placeholder={kind === "folder" ? "Paste a folder path" : "Paste a video file path"} required />
        </Field>

        <div className="grid gap-3 sm:grid-cols-2">
          {([
            { value: "reference", icon: Link2, title: "Keep in place", text: "Uses the file where it is. Saves disk space. Don’t move or delete the original." },
            { value: "copy", icon: Copy, title: "Copy into library", text: "Safer: the app keeps its own copy. Uses extra disk space." },
          ] as const).map(({ value, icon: Icon, title, text }) => (
            <label key={value} className={cx("cursor-pointer rounded-xl border p-3 transition", mode === value ? "border-brand-500 bg-brand-500/10" : "border-ink-600 hover:bg-ink-850")}>
              <input type="radio" name="mode" value={value} checked={mode === value} onChange={() => setMode(value)} className="sr-only" />
              <div className="flex items-center gap-2 text-sm font-medium text-zinc-100"><Icon className="h-4 w-4" />{title}</div>
              <p className="mt-1 text-xs text-zinc-400">{text}</p>
            </label>
          ))}
        </div>

        {kind === "folder" && (
          <label className="flex items-center gap-2 text-sm text-zinc-300">
            <input type="checkbox" checked={recursive} onChange={(e) => setRecursive(e.target.checked)} className="h-4 w-4 accent-pink-500" />
            Also look inside sub-folders
          </label>
        )}

        <Button type="submit" variant="primary" loading={busy} disabled={!path.trim()}>
          <FolderOpen className="h-4 w-4" /> {kind === "folder" ? "Scan & import folder" : "Import file"}
        </Button>
      </form>

      <div className="mt-4 space-y-3">
        {error && <Alert onClose={() => setError(null)}>{error}</Alert>}
        {single && (
          <Alert tone={single.status === "imported" ? "success" : "warning"}>
            {single.message} {single.video && <Link className="underline" href={`/library/${single.video.id}`}>Open video</Link>}
          </Alert>
        )}
        {folder && (
          <div className="space-y-2">
            <Alert tone={folder.found === 0 ? "warning" : folder.summary.error ? "warning" : "success"}>
              {folder.found === 0
                ? "No video files found in that folder."
                : `Found ${folder.found} video(s): ${folder.summary.imported} imported, ${folder.summary.duplicate} already in library, ${folder.summary.error} failed.`}
            </Alert>
            <ul className="max-h-64 space-y-1 overflow-y-auto text-xs">
              {folder.results.map((r) => (
                <li key={r.path} className="flex items-center gap-2 rounded-lg bg-ink-850 px-3 py-1.5">
                  {r.status === "imported" ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" /> : r.status === "duplicate" ? <Copy className="h-3.5 w-3.5 shrink-0 text-amber-400" /> : <XCircle className="h-3.5 w-3.5 shrink-0 text-red-400" />}
                  <span className="truncate text-zinc-300" title={r.path}>{r.path?.split(/[\\/]/).pop()}</span>
                  <span className="ml-auto shrink-0 text-zinc-500">{r.status === "error" ? r.message : r.status}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Card>
  );
}
