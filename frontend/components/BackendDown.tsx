import { Alert } from "./ui";

export function BackendDown({ error }: { error: string }) {
  return (
    <Alert tone="error">
      <div className="font-medium">The dashboard cannot talk to the backend.</div>
      <div className="mt-1 text-red-200/80">{error}</div>
      <div className="mt-2 text-red-200/80">
        Fix: run <code className="rounded bg-black/30 px-1">scripts/start</code> (or <code className="rounded bg-black/30 px-1">start-windows.bat</code>) and keep that window open.
      </div>
    </Alert>
  );
}
