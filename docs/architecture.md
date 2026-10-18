# Architecture

```
src/echotrace/
├── app.py            entry point: logging + Qt application
├── paths.py          per-OS directories (ECHOTRACE_HOME override)
├── network.py        verified TLS session, headers, proxies, delays, fetch()
├── config/           Settings (JSON), input scoring table
├── core/
│   ├── engine.py     EchoTraceEngine: runs modules in parallel, verifies profiles, stores results
│   ├── verify.py     re-reads found profiles: name/company/city/same-picture evidence, login walls
│   ├── compare.py    diff between two analyses
│   ├── identity.py   target fingerprint, purposes, helpers to split pseudos and photos
│   └── scorer.py     input validation and result confidence
├── cli.py            echotrace-cli (same engine as the GUI)
├── database/db.py    SQLite: targets, searches, results, cache
├── modules/          one file per data source (see modules.md)
├── reports/          HTML, JSON, CSV, PDF, SVG graph
└── ui/               PyQt6 window, settings dialog, worker thread, theme
```

## Flow of an analysis

1. The UI collects the form into a `dict` (`pseudo`, `email`, ...) and validates it with
   `is_input_valid` (score threshold + at least two fields).
2. `AnalysisThread` runs `EchoTraceEngine.run_analysis` in its own asyncio loop so the UI never blocks.
3. The engine saves the target, then starts every module whose `can_run()` is true as an asyncio task
   sharing one `aiohttp` session.
4. Each module returns `OsintResult` objects; the engine drops URLs marked as false positives for
   this target, writes the rest to SQLite and streams them to the UI right away.
5. Unless cancelled, `core/verify.py` re-reads the found profiles and updates their confidence.
   Progress is aggregated (modules 0-85 %, verification 85-98 %) and sent through a Qt signal.
6. `stop_analysis()` (any thread) cancels the tasks through `loop.call_soon_threadsafe`; results of
   modules that finished are kept.
7. The engine compares the rows with the previous analysis of the same target (`target_key`) and
   returns the diff; the UI displays the rows read back from the database.

## Data

SQLite tables: `targets` (input and score), `searches` (one row per module run and its status),
`results`, and `cache` (key/value with expiry, used for username checks). Deleting a target
cascades to its searches and results. Connections are short-lived (`db.get_conn()` closes them).

## Design choices

- Everything that writes goes to per-user directories, never next to the code: frozen binaries may
  live in read-only locations.
- TLS verification is on, with the certifi bundle, so frozen builds behave the same on every OS.
- Reports escape all scraped text (Jinja2 autoescape, SVG escaping, CSV formula neutralisation) and
  only link `http(s)` URLs.
- No heavy optional features in the base install: OpenCV is an extra, the graph is plain SVG.
