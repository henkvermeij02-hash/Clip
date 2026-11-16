"use client";

import {
  BarChart3, Clapperboard, FileText, Film, LayoutDashboard, ListChecks, Menu, Scale, Settings,
  Sparkles, Upload, UploadCloud, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { cx } from "./ui";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/import", label: "Import footage", icon: Upload },
  { href: "/library", label: "Library", icon: Film },
  { href: "/jobs", label: "Background jobs", icon: ListChecks },
  { href: "/rights", label: "Rights & licences", icon: Scale },
  { href: "/settings", label: "Settings", icon: Settings },
];

// Not built yet — shown so you can see where the app is heading. Not clickable.
const UPCOMING = [
  { label: "Moment finder", phase: 2, icon: Sparkles },
  { label: "Scripts & voice", phase: 3, icon: FileText },
  { label: "Shorts editor", phase: 4, icon: Clapperboard },
  { label: "Approval & upload", phase: 5, icon: UploadCloud },
  { label: "Analytics", phase: 6, icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  const nav = (
    <nav className="flex h-full flex-col gap-6 p-4">
      <Link href="/" className="flex items-center gap-3 px-2 pt-2" onClick={() => setOpen(false)}>
        <div className="brand-gradient flex h-9 w-9 items-center justify-center rounded-xl font-black text-white shadow-lg shadow-brand-500/30">GS</div>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-white">GTA Shorts</div>
          <div className="text-xs text-brand-gradient font-semibold">AI Studio</div>
        </div>
      </Link>

      <div className="space-y-1">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            onClick={() => setOpen(false)}
            className={cx(
              "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition",
              isActive(href) ? "bg-ink-800 text-white ring-1 ring-ink-600" : "text-zinc-400 hover:bg-ink-850 hover:text-zinc-100",
            )}
          >
            <Icon className={cx("h-4 w-4", isActive(href) && "text-brand-400")} />
            {label}
          </Link>
        ))}
      </div>

      <div>
        <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">Coming in later phases</div>
        <div className="space-y-1">
          {UPCOMING.map(({ label, phase, icon: Icon }) => (
            <div key={label} className="flex cursor-not-allowed items-center gap-3 rounded-xl px-3 py-2 text-sm text-zinc-600" title={`Not built yet — planned for Phase ${phase}`} aria-disabled>
              <Icon className="h-4 w-4" />
              <span className="flex-1">{label}</span>
              <span className="rounded-md bg-ink-850 px-1.5 py-0.5 text-[10px] font-semibold text-zinc-500">P{phase}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-auto rounded-xl border border-ink-700 bg-ink-850 p-3 text-xs text-zinc-500">
        Everything runs on your computer. Nothing is uploaded without your approval.
      </div>
    </nav>
  );

  return (
    <>
      <div className="sticky top-0 z-30 flex items-center justify-between border-b border-ink-700 bg-ink-950/90 px-4 py-3 backdrop-blur lg:hidden">
        <span className="text-sm font-semibold text-white">GTA Shorts <span className="text-brand-gradient">AI Studio</span></span>
        <button onClick={() => setOpen(true)} className="rounded-lg p-2 text-zinc-300 hover:bg-ink-800" aria-label="Open menu">
          <Menu className="h-5 w-5" />
        </button>
      </div>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 overflow-y-auto border-r border-ink-700 bg-ink-900">
            <button onClick={() => setOpen(false)} className="absolute right-3 top-4 rounded-lg p-2 text-zinc-400 hover:bg-ink-800" aria-label="Close menu">
              <X className="h-5 w-5" />
            </button>
            {nav}
          </aside>
        </div>
      )}
      <aside className="fixed inset-y-0 left-0 hidden w-64 overflow-y-auto border-r border-ink-700 bg-ink-900/60 lg:block">{nav}</aside>
    </>
  );
}
