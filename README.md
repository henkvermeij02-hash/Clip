# GTA Shorts AI Studio

A local-first studio that turns **your own** GTA gameplay recordings into YouTube Shorts.
It runs entirely on your computer, uses only free tools, and **never uploads anything
without your explicit approval**.

> **Status: Phase 1 of 6 is built.** You can import footage, the app reads every
> video's details in the background, and you can browse, watch and track rights for
> your recordings. AI moment detection, scripts, voice, editing and YouTube upload
> come in later phases (see [Roadmap](#roadmap)).

---

## What works today (Phase 1)

| Feature | Details |
|---|---|
| Dashboard | Stats, recent recordings, active/failed jobs, setup check (FFmpeg, worker, Ollama) |
| Upload from browser | Drag & drop, any size (streamed straight to disk), progress bar, one file at a time |
| Import from a folder | Paste a folder or file path. **Keep in place** (no extra disk space) or **Copy into library** |
| Duplicate protection | The same recording is never imported twice, even if it's renamed |
| Metadata extraction | FFprobe reads length, resolution, frame rate, codecs, audio, bitrate; a thumbnail is made |
| Background jobs | Persistent queue in SQLite: survives restarts, automatic retry, cancel & retry buttons, clear error messages |
| Library | Search, filter by status, in-browser player with seeking, video details |
| Rights tracking | Per video: source, monetisation status, notes, confirmation. Licence register for music/SFX/voices/fonts |
| Settings | Folders, FFmpeg path, worker count, video format, Ollama models (with connection test), Piper/Whisper, default YouTube privacy (private) |

## Requirements (all free)

| Program | Why | Get it |
|---|---|---|
| **Python 3.11+** | Runs the backend | <https://www.python.org/downloads/> — on Windows tick **“Add python.exe to PATH”** |
| **Node.js 20+ (LTS)** | Runs the dashboard | <https://nodejs.org/> |
| **FFmpeg** (includes FFprobe) | Reads and edits video | Windows: `winget install Gyan.FFmpeg` · Mac: `brew install ffmpeg` · Linux: `sudo apt install ffmpeg` |
| **Git** | Downloads this project and updates | <https://git-scm.com/> |
| Ollama *(from Phase 2, optional now)* | Local AI that looks at your footage | <https://ollama.com/> |

**No paid services, API keys or subscriptions are needed.**

## Installation

1. Open a terminal (Windows: press Start, type **PowerShell**, open it).
2. Download the project:
   ```
   git clone https://github.com/henkvermeij02-hash/Clip.git
   cd Clip
   ```
3. Run setup **once**:
   - **Windows:** double-click `setup-windows.bat` (or type `.\setup-windows.bat`)
   - **Mac / Linux:** `./scripts/setup.sh`

   It checks Python, Node.js and FFmpeg, then installs everything else. If a program is
   missing, it tells you which one.

## Starting the studio

- **Windows:** double-click `start-windows.bat`. Two windows open (backend and dashboard) — keep them open. Your browser opens <http://localhost:3000>.
- **Mac / Linux:** `./scripts/start.sh`, then open <http://localhost:3000>. Press `Ctrl+C` to stop.

The first page load takes a few seconds while the dashboard compiles.

### Your first import
1. Go to **Import footage**.
2. Either drag a recording into the upload box, or paste the path of the folder where your
   captures are (Windows tip: right-click the folder in Explorer → **Copy as path**).
3. Watch the **Background jobs** page: each video is read and gets a thumbnail.
4. Open the video in the **Library** and fill in **Rights & permissions**.

> GTA 6 launches on consoles first. Transfer your captures from the console to your
> computer (USB drive or the console's capture sharing) and import that folder.

## Where your files are

Everything stays on your computer, in the `data/` folder inside the project
(never committed to git):

```
data/
  studio.db      ← the database (videos, jobs, settings, licences)
  library/       ← uploaded / copied recordings
  thumbnails/
  renders/       ← finished Shorts (Phase 4)
```

You can move the library and render folders on the **Settings** page (e.g. to a big external
drive). “Keep in place” imports are never moved or deleted by the app; removing such a video
only removes it from the library.

## Troubleshooting

| Problem | Fix |
|---|---|
| Dashboard says it **cannot reach the backend** | The backend window is closed or crashed. Start again with the start script and read the backend window's messages. |
| **FFmpeg not found** in the setup check | Install FFmpeg, then restart your terminal. Or enter the full path to `ffmpeg.exe` / `ffprobe.exe` on Settings → Tools. |
| A video shows **Error** | Open it — the message says what went wrong (e.g. damaged file). Fix it and press **Retry** on the job. |
| Video doesn't **play** in the browser | Some formats (MKV, HEVC) can't play in every browser. Processing still works. |
| Port 3000 or 8000 **already in use** | Another copy is running. Close it first. |

## Running the tests

```
./scripts/test.sh                      # Mac / Linux
cd backend && .venv\Scripts\python -m pytest   # Windows
```

The tests create small real videos with FFmpeg and check import, duplicate detection,
metadata extraction, the job queue (retry, cancel, resume after restart), settings
validation and the licence register.

## Rights & licensing — important

Recording gameplay yourself does **not automatically** give you the right to monetise it.
The publisher owns the game's art, music and characters and sets the rules for gameplay
videos; in-game radio music is a common source of copyright claims. The app tracks each
recording's rights status and a licence register for music, sound effects and voices
(Piper voices each have their own licence). Later phases will only use assets recorded
there. This app is a tracking tool, not legal advice.

## What needs internet, hardware or accounts

| Feature | Internet | Hardware | Account |
|---|---|---|---|
| Phase 1 (everything above) | Only for installation | Any computer | None |
| AI analysis & scripts (Ollama, Phase 2–3) | Only to download models once | 16 GB RAM recommended; a GPU with 8 GB+ VRAM makes it much faster | None |
| Voice (Piper) & subtitles (faster-whisper) (Phase 3) | Only to download models once | Runs on CPU; GPU optional | None |
| YouTube upload & analytics (Phase 5–6) | Yes | – | Your Google account + a free Google Cloud project for the official YouTube Data API |

## Roadmap

- [x] **Phase 1 — Foundation:** dashboard, backend, database, import, metadata, jobs, settings, rights
- [ ] **Phase 2 — Video intelligence:** scene detection (PySceneDetect), frame sampling (OpenCV), Ollama vision analysis, suggested clips with timestamps & confidence
- [ ] **Phase 3 — AI content:** original narration scripts, Piper voice, faster-whisper subtitles
- [ ] **Phase 4 — Automatic editing:** vertical 9:16 render, subtitles, voiceover, branding, previews, quality checks
- [ ] **Phase 5 — Approval & YouTube:** approval dashboard, official OAuth, private-by-default uploads, upload history
- [ ] **Phase 6 — Analytics:** YouTube performance data and data-driven suggestions

## Project layout

```
backend/                 Python + FastAPI
  app/main.py            app startup, starts the background worker
  app/config.py          folders and all settings (with validation)
  app/db.py              SQLite database + migrations
  app/jobs.py            persistent background job queue
  app/services/          media (FFprobe/FFmpeg), hashing, video import
  app/routers/           API endpoints: videos, jobs, settings/system, licences
  tests/                 automated tests
frontend/                Next.js + TypeScript + Tailwind dashboard
  app/                   pages: dashboard, import, library, jobs, rights, settings
  components/ lib/       shared UI and the API client
scripts/                 setup/start/test for Mac & Linux
setup-windows.bat        one-time setup on Windows
start-windows.bat        start on Windows
docs/ARCHITECTURE.md     how the pieces fit together
```

The backend API documentation is available at <http://localhost:8000/docs> while it runs.
