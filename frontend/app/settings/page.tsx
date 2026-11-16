"use client";

import { PlugZap, RotateCcw, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { BackendDown } from "@/components/BackendDown";
import { Alert, Badge, Button, Card, Field, PageHeader, Spinner, inputClass } from "@/components/ui";
import { post, put, type SettingSchema, type SettingsResponse } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";

const GROUPS: { key: string; title: string; subtitle: string }[] = [
  { key: "folders", title: "Folders", subtitle: "Where footage and finished Shorts are stored on this computer." },
  { key: "tools", title: "Tools & performance", subtitle: "FFmpeg location and how much work runs in parallel." },
  { key: "video", title: "Video", subtitle: "Output format for Shorts and clip length limits." },
  { key: "ai", title: "Local AI models (Ollama)", subtitle: "Free models that run on your own computer. Needs a decent GPU or patience on CPU." },
  { key: "voice", title: "Voice & subtitles", subtitle: "Piper text-to-speech and faster-whisper transcription — both run locally." },
  { key: "branding", title: "Branding", subtitle: "Optional watermark text on your Shorts." },
  { key: "youtube", title: "YouTube", subtitle: "Uploading is always manual-approval only." },
];

type Values = SettingsResponse["values"];

export default function SettingsPage() {
  const { data, error, setData } = usePolling<SettingsResponse>("/api/settings", 0);
  const [draft, setDraft] = useState<Values>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  useEffect(() => { if (data) setDraft(data.values); }, [data]);

  const changed = useMemo(() => {
    if (!data) return {};
    return Object.fromEntries(Object.entries(draft).filter(([k, v]) => String(v) !== String(data.values[k])));
  }, [draft, data]);
  const dirty = Object.keys(changed).length > 0;

  async function save() {
    setSaving(true);
    setMessage(null);
    try {
      const res = await put<SettingsResponse>("/api/settings", { values: changed });
      setData(res);
      setMessage({ tone: "success", text: "Settings saved." });
    } catch (e) {
      setMessage({ tone: "error", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setSaving(false);
    }
  }

  if (error && !data) return <><PageHeader title="Settings" /><BackendDown error={error} /></>;
  if (!data) return <Spinner />;

  return (
    <>
      <PageHeader
        title="Settings"
        description="Settings are saved in your local database. Items marked with a phase are stored now and used once that phase is built."
        actions={
          <>
            <Button variant="ghost" onClick={() => setDraft(data.values)} disabled={!dirty}><RotateCcw className="h-4 w-4" />Undo changes</Button>
            <Button variant="primary" onClick={save} loading={saving} disabled={!dirty}><Save className="h-4 w-4" />Save settings</Button>
          </>
        }
      />
      {message && <div className="mb-6"><Alert tone={message.tone} onClose={() => setMessage(null)}>{message.text}</Alert></div>}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {GROUPS.map((group) => {
          const items = data.schema.filter((s) => s.group === group.key);
          if (!items.length) return null;
          return (
            <Card key={group.key} title={group.title} subtitle={group.subtitle}>
              <div className="space-y-4">
                {items.map((spec) => (
                  <SettingInput key={spec.key} spec={spec} value={draft[spec.key]} onChange={(v) => setDraft((d) => ({ ...d, [spec.key]: v }))} />
                ))}
                {group.key === "ai" && <OllamaTest url={String(draft.ollama_url ?? "")} />}
                {group.key === "youtube" && (
                  <Alert tone="warning">
                    Connecting your YouTube channel (official Google OAuth) is built in <strong>Phase 5</strong>. It will need a free Google Cloud project and internet access. Nothing is ever uploaded without your explicit approval.
                  </Alert>
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </>
  );
}

function SettingInput({ spec, value, onChange }: { spec: SettingSchema; value: unknown; onChange: (v: string | number) => void }) {
  const id = `setting-${spec.key}`;
  const label = (
    <span className="flex items-center gap-2">
      {spec.label}
      {spec.phase > 1 && <Badge>used from Phase {spec.phase}</Badge>}
    </span>
  );
  const help = <>{spec.help}{String(value) !== String(spec.default) && <span className="ml-1 text-zinc-600">Default: {String(spec.default)}</span>}</>;
  if (spec.choices) {
    return (
      <Field label={label} help={help} htmlFor={id}>
        <select id={id} className={inputClass} value={String(value ?? "")} onChange={(e) => onChange(spec.type === "int" ? Number(e.target.value) : e.target.value)}>
          {spec.choices.map((c) => <option key={String(c)} value={String(c)}>{String(c)}</option>)}
        </select>
      </Field>
    );
  }
  return (
    <Field label={label} help={help} htmlFor={id}>
      <input
        id={id}
        className={inputClass}
        type={spec.type === "int" ? "number" : "text"}
        min={spec.minimum ?? undefined}
        max={spec.maximum ?? undefined}
        value={String(value ?? "")}
        onChange={(e) => onChange(spec.type === "int" ? (e.target.value === "" ? "" : Number(e.target.value)) as number : e.target.value)}
      />
    </Field>
  );
}

interface OllamaResult { available: boolean; models: string[]; error: string | null; vision_model_installed?: boolean; text_model_installed?: boolean }

function OllamaTest({ url }: { url: string }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<OllamaResult | null>(null);
  async function test() {
    setBusy(true);
    try { setResult(await post<OllamaResult>("/api/settings/test-ollama", { url })); }
    catch (e) { setResult({ available: false, models: [], error: e instanceof Error ? e.message : String(e) }); }
    finally { setBusy(false); }
  }
  return (
    <div className="space-y-3">
      <Button onClick={test} loading={busy}><PlugZap className="h-4 w-4" />Test Ollama connection</Button>
      {result && (result.available ? (
        <Alert tone="success">
          Connected. Installed models: {result.models.length ? result.models.join(", ") : "none yet"}.
          {result.vision_model_installed === false && <div className="mt-1">The vision model is not installed yet (save settings first if you changed it). Run <code>ollama pull &lt;model&gt;</code>.</div>}
          {result.text_model_installed === false && <div>The text model is not installed yet.</div>}
        </Alert>
      ) : <Alert>{result.error} Ollama is only needed from Phase 2.</Alert>)}
    </div>
  );
}
