"use client";

import { ListChecks } from "lucide-react";
import { useState } from "react";
import { BackendDown } from "@/components/BackendDown";
import { JobList } from "@/components/JobList";
import { EmptyState, PageHeader, Spinner, cx } from "@/components/ui";
import type { Job } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";

const FILTERS = [
  { value: "", label: "All" },
  { value: "queued,running", label: "Active" },
  { value: "failed", label: "Failed" },
  { value: "succeeded", label: "Done" },
  { value: "cancelled", label: "Cancelled" },
];

export default function JobsPage() {
  const [status, setStatus] = useState("");
  const { data, error, loading, reload } = usePolling<Job[]>(`/api/jobs?limit=200${status ? `&status=${status}` : ""}`, 2000);
  return (
    <>
      <PageHeader
        title="Background jobs"
        description="Long tasks (copying, reading metadata, and later AI analysis and rendering) run here without blocking the dashboard. They survive restarts: if the app stops mid-task, it continues when you start it again."
      />
      <div className="mb-4 flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button key={f.value} onClick={() => setStatus(f.value)} className={cx("rounded-lg px-3 py-1.5 text-sm transition", status === f.value ? "bg-ink-700 text-white" : "text-zinc-400 hover:bg-ink-850")}>{f.label}</button>
        ))}
      </div>
      {error && !data && <BackendDown error={error} />}
      {loading && !data ? <Spinner /> : data && data.length ? <JobList jobs={data} onChange={reload} /> : data ? (
        <EmptyState icon={<ListChecks className="h-8 w-8" />} title="No jobs here" />
      ) : null}
    </>
  );
}
