// Talks to the FastAPI backend running on this computer.
export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors
    return detail.map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: string }).msg) : String(d))).join("; ");
  }
  return "Unexpected response from the backend.";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { ...(init.body && typeof init.body === "string" ? { "Content-Type": "application/json" } : {}), ...init.headers },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Cannot reach the backend at ${API_URL}. Is it running? Start it with the start script (see README).`,
      0,
    );
  }
  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) {
    const detail = data && typeof data === "object" && "detail" in data ? (data as { detail: unknown }).detail : text;
    throw new ApiError(describe(detail) || `Request failed (${res.status})`, res.status);
  }
  return data as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export const post = <T,>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
export const put = <T,>(path: string, body: unknown) => api<T>(path, { method: "PUT", body: JSON.stringify(body) });
export const patch = <T,>(path: string, body: unknown) => api<T>(path, { method: "PATCH", body: JSON.stringify(body) });
export const del = <T,>(path: string) => api<T>(path, { method: "DELETE" });

/** Upload a file with progress reporting. The raw file is streamed to the backend. */
export function uploadFile(
  file: File,
  onProgress: (fraction: number) => void,
): { promise: Promise<ImportResult>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<ImportResult>((resolve, reject) => {
    xhr.open("PUT", `${API_URL}/api/videos/upload?filename=${encodeURIComponent(file.name)}`);
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      const data = safeJson(xhr.responseText) as ImportResult & { detail?: unknown };
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new ApiError(describe(data?.detail) || `Upload failed (${xhr.status})`, xhr.status));
    };
    xhr.onerror = () => reject(new ApiError(`Upload failed: cannot reach the backend at ${API_URL}.`, 0));
    xhr.onabort = () => reject(new ApiError("Upload cancelled.", 0));
    xhr.send(file);
  });
  return { promise, abort: () => xhr.abort() };
}

// ---------------------------------------------------------------- types

export type VideoStatus = "pending" | "processing" | "ready" | "error";
export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface Job {
  id: number;
  type: string;
  label: string;
  status: JobStatus;
  video_id: number | null;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
  progress: number;
  message: string | null;
  error: string | null;
  error_detail: string | null;
  attempts: number;
  max_attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string;
}

export interface Video {
  id: number;
  title: string | null;
  original_filename: string;
  file_path: string;
  storage_mode: "copied" | "referenced";
  file_size: number;
  status: VideoStatus;
  error: string | null;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  video_codec: string | null;
  audio_codec: string | null;
  has_audio: boolean | null;
  bitrate: number | null;
  container: string | null;
  has_thumbnail: boolean;
  file_exists: boolean;
  rights_source: "own_recording" | "licensed" | "other";
  rights_confirmed: boolean;
  monetization_status: "unknown" | "not_monetized" | "cleared" | "not_allowed";
  rights_notes: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  jobs?: Job[];
}

export interface ImportResult {
  status: "imported" | "duplicate" | "error";
  message: string;
  video: Video | null;
  job: Job | null;
  path?: string;
}

export interface FolderImportResult {
  folder: string;
  found: number;
  summary: { imported: number; duplicate: number; error: number };
  results: ImportResult[];
}

export interface ToolStatus {
  available: boolean;
  path: string | null;
  version: string | null;
  error: string | null;
}

export interface SystemStatus {
  ffmpeg: ToolStatus;
  ffprobe: ToolStatus;
  ollama: { available: boolean; models: string[]; error: string | null };
  worker_running: boolean;
  data_dir: string;
  library_dir: string;
  disk: { folder: string; free_bytes: number; total_bytes: number };
}

export interface Stats {
  videos: {
    total: number;
    ready: number;
    processing: number;
    errors: number;
    total_seconds: number;
    library_bytes: number;
    rights_unconfirmed: number;
  };
  jobs: { queued: number; running: number; failed: number };
}

export interface SettingSchema {
  key: string;
  default: string | number | boolean;
  type: "str" | "int" | "bool";
  group: string;
  label: string;
  help: string;
  phase: number;
  choices: (string | number)[] | null;
  minimum: number | null;
  maximum: number | null;
}

export interface SettingsResponse {
  values: Record<string, string | number | boolean>;
  schema: SettingSchema[];
}

export interface License {
  id: number;
  asset_type: string;
  name: string;
  source_url: string | null;
  license_name: string;
  license_url: string | null;
  allows_commercial: boolean;
  attribution_required: boolean;
  attribution_text: string | null;
  file_path: string | null;
  notes: string | null;
  created_at: string;
}
