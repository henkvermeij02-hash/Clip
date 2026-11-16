"use client";

import { Film, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { BackendDown } from "@/components/BackendDown";
import { EmptyState, PageHeader, Spinner, cx, inputClass } from "@/components/ui";
import { VideoCard } from "@/components/VideoCard";
import type { Video } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";

const FILTERS = [
  { value: "", label: "All" },
  { value: "ready", label: "Ready" },
  { value: "processing", label: "Processing" },
  { value: "pending", label: "Waiting" },
  { value: "error", label: "Errors" },
];

export default function LibraryPage() {
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (debounced) params.set("q", debounced);
  const { data, error, loading } = usePolling<Video[]>(`/api/videos?${params}`, 4000);

  return (
    <>
      <PageHeader
        title="Footage library"
        description="All imported recordings. Click a video to watch it, see its details and record its rights status."
        actions={<Link href="/import" className="brand-gradient rounded-xl px-4 py-2 text-sm font-medium text-white">Import more</Link>}
      />
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative sm:w-80">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
          <input className={cx(inputClass, "pl-9")} placeholder="Search by title or filename" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button key={f.value} onClick={() => setStatus(f.value)} className={cx("rounded-lg px-3 py-1.5 text-sm transition", status === f.value ? "bg-ink-700 text-white" : "text-zinc-400 hover:bg-ink-850")}>
              {f.label}
            </button>
          ))}
        </div>
      </div>
      {error && !data && <BackendDown error={error} />}
      {loading && !data ? <Spinner /> : data && data.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {data.map((v) => <VideoCard key={v.id} video={v} />)}
        </div>
      ) : data ? (
        <EmptyState icon={<Film className="h-8 w-8" />} title={status || debounced ? "No videos match" : "Your library is empty"}>
          {!status && !debounced && <Link href="/import" className="text-brand-400 hover:underline">Import gameplay footage</Link>}
        </EmptyState>
      ) : null}
    </>
  );
}
