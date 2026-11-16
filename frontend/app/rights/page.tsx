"use client";

import { Plus, Scale, Trash2 } from "lucide-react";
import { useState } from "react";
import { BackendDown } from "@/components/BackendDown";
import { Alert, Badge, Button, Card, EmptyState, Field, PageHeader, Spinner, inputClass } from "@/components/ui";
import { del, post, type License } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";

const TYPES = [
  ["music", "Music"], ["sfx", "Sound effect"], ["voice", "TTS voice"], ["font", "Font"],
  ["logo", "Logo / image"], ["model", "AI model"], ["other", "Other"],
] as const;

const empty = {
  asset_type: "music", name: "", license_name: "", source_url: "", license_url: "",
  allows_commercial: false, attribution_required: false, attribution_text: "", notes: "",
};

export default function RightsPage() {
  const { data, error, reload } = usePolling<License[]>("/api/licenses", 0);
  const [form, setForm] = useState(empty);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      await post("/api/licenses", form);
      setForm(empty);
      reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(l: License) {
    if (!window.confirm(`Delete the licence record for "${l.name}"?`)) return;
    try { await del(`/api/licenses/${l.id}`); reload(); }
    catch (err) { setFormError(err instanceof Error ? err.message : String(err)); }
  }

  const set = (k: keyof typeof empty, v: string | boolean) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <>
      <PageHeader title="Rights & licences" description="Keep track of what you are allowed to use. Later phases will only use music, sound effects and voices that are recorded here." />

      <Card title="Gameplay footage — read this first" className="mb-6">
        <div className="space-y-2 text-sm text-zinc-300">
          <p>Recording gameplay yourself does <strong>not automatically</strong> give you the right to monetise it. The game’s publisher owns the game’s art, music and characters, and decides what video creators may do.</p>
          <ul className="list-disc space-y-1 pl-5 text-zinc-400">
            <li>Read the publisher’s current policy on gameplay videos before monetising, and save the link and date in each video’s rights notes.</li>
            <li>In-game radio music is often licensed separately and can trigger copyright claims. Consider muting or replacing it.</li>
            <li>YouTube’s monetisation rules expect your own commentary and editing to add value — the AI scripts help, but you are responsible for the final video.</li>
            <li>This app is a tracking tool, not legal advice.</li>
          </ul>
          <p className="text-zinc-400">Each video’s status is set on its page in the <a href="/library" className="text-brand-400 hover:underline">Library</a>.</p>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-5">
        <Card title="Add a licence" subtitle="Music, sound effects, TTS voices, fonts, logos or AI models." className="xl:col-span-2">
          <form onSubmit={add} className="space-y-4">
            <Field label="Type" htmlFor="type">
              <select id="type" className={inputClass} value={form.asset_type} onChange={(e) => set("asset_type", e.target.value)}>
                {TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Field>
            <Field label="Name" htmlFor="name"><input id="name" required className={inputClass} value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. Piper en_US-lessac-medium" /></Field>
            <Field label="Licence" htmlFor="lic"><input id="lic" required className={inputClass} value={form.license_name} onChange={(e) => set("license_name", e.target.value)} placeholder="e.g. CC BY 4.0, CC0, YouTube Audio Library" /></Field>
            <Field label="Where you got it (URL)" htmlFor="src"><input id="src" className={inputClass} value={form.source_url} onChange={(e) => set("source_url", e.target.value)} /></Field>
            <Field label="Licence text URL" htmlFor="licurl"><input id="licurl" className={inputClass} value={form.license_url} onChange={(e) => set("license_url", e.target.value)} /></Field>
            <label className="flex items-center gap-2 text-sm text-zinc-300"><input type="checkbox" className="h-4 w-4 accent-pink-500" checked={form.allows_commercial} onChange={(e) => set("allows_commercial", e.target.checked)} />Allows commercial / monetised use</label>
            <label className="flex items-center gap-2 text-sm text-zinc-300"><input type="checkbox" className="h-4 w-4 accent-pink-500" checked={form.attribution_required} onChange={(e) => set("attribution_required", e.target.checked)} />Requires attribution (credit)</label>
            {form.attribution_required && (
              <Field label="Attribution text" htmlFor="attr" help="Will be added to video descriptions in Phase 5."><textarea id="attr" className={inputClass} rows={2} value={form.attribution_text} onChange={(e) => set("attribution_text", e.target.value)} /></Field>
            )}
            <Field label="Notes" htmlFor="lnotes"><textarea id="lnotes" className={inputClass} rows={2} value={form.notes} onChange={(e) => set("notes", e.target.value)} /></Field>
            {formError && <Alert onClose={() => setFormError(null)}>{formError}</Alert>}
            <Button type="submit" variant="primary" loading={busy}><Plus className="h-4 w-4" />Add licence</Button>
          </form>
        </Card>

        <Card title="Licence register" className="xl:col-span-3">
          {error && !data ? <BackendDown error={error} /> : !data ? <Spinner /> : data.length === 0 ? (
            <EmptyState icon={<Scale className="h-8 w-8" />} title="No licences recorded yet">Add the voices, music and sound effects you plan to use.</EmptyState>
          ) : (
            <ul className="space-y-3">
              {data.map((l) => (
                <li key={l.id} className="rounded-xl border border-ink-700 bg-ink-850 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-zinc-100">{l.name}</span>
                        <Badge>{TYPES.find(([v]) => v === l.asset_type)?.[1] ?? l.asset_type}</Badge>
                        {l.allows_commercial ? <Badge tone="emerald">Commercial OK</Badge> : <Badge tone="amber">No commercial use</Badge>}
                        {l.attribution_required && <Badge tone="brand">Credit required</Badge>}
                      </div>
                      <div className="mt-1 text-sm text-zinc-400">{l.license_name}</div>
                      {l.attribution_text && <div className="mt-1 text-xs text-zinc-500">Credit: {l.attribution_text}</div>}
                      {l.source_url && <a href={l.source_url} target="_blank" rel="noreferrer" className="mt-1 block truncate text-xs text-brand-400 hover:underline">{l.source_url}</a>}
                      {l.notes && <div className="mt-1 text-xs text-zinc-500">{l.notes}</div>}
                    </div>
                    <Button variant="ghost" className="px-2" onClick={() => remove(l)} aria-label="Delete"><Trash2 className="h-4 w-4" /></Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
